"""Reference annotations and honest, non-destructive shortlist evaluation."""
import copy
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen
from unittest.mock import patch

from engine import Studio


class QualityAlgorithmTests(unittest.TestCase):
    def test_evaluates_reference_intervals_one_to_one_with_iou_threshold(self):
        from quality_benchmark import evaluate_quality
        references = [
            {'id': 'r1', 'media_id': 'm1', 'start': 10, 'end': 20},
            {'id': 'r2', 'media_id': 'm1', 'start': 40, 'end': 50},
        ]
        clips = [
            {'id': 'c1', 'media_id': 'm1', 'start': 10, 'end': 20, 'enabled': True},
            {'id': 'c2', 'media_id': 'm1', 'start': 11, 'end': 19, 'enabled': True},
            {'id': 'c3', 'media_id': 'm1', 'start': 70, 'end': 80, 'enabled': True},
            {'id': 'c4', 'media_id': 'm1', 'start': 40, 'end': 50, 'enabled': False},
            {'id': 'c5', 'media_id': 'm2', 'start': 40, 'end': 50, 'enabled': True},
        ]
        result = evaluate_quality(references, clips)
        self.assertTrue(result['ready'])
        self.assertEqual((result['references'], result['predictions'], result['matched']), (2, 3, 1))
        self.assertAlmostEqual(result['precision'], 1/3, places=4)
        self.assertAlmostEqual(result['recall'], .5)
        self.assertAlmostEqual(result['f1'], .4, places=3)
        self.assertEqual(result['excluded_unlabelled_clips'], 1)
        self.assertEqual(result['matches'][0]['clip_id'], 'c1')
        self.assertEqual(result['missed_references'][0]['id'], 'r2')

    def test_no_annotations_is_unmeasured_not_zero_quality(self):
        from quality_benchmark import evaluate_quality
        result = evaluate_quality([], [{'id':'c1','media_id':'m1','start':0,'end':5,'enabled':True}])
        self.assertFalse(result['ready'])
        self.assertIsNone(result['precision'])
        self.assertIsNone(result['recall'])
        self.assertIsNone(result['f1'])

    def test_matching_does_not_reuse_one_clip_for_two_references(self):
        from quality_benchmark import evaluate_quality
        refs = [{'id':'r1','media_id':'m1','start':0,'end':5},
                {'id':'r2','media_id':'m1','start':5,'end':10}]
        clips = [{'id':'c1','media_id':'m1','start':2,'end':8,'enabled':True}]
        self.assertEqual(evaluate_quality(refs,clips)['matched'],1)

    def test_matching_finds_two_pairings_not_only_best_global_edge(self):
        from quality_benchmark import evaluate_quality
        refs = [{'id':'r1','media_id':'m1','start':0,'end':10},
                {'id':'r2','media_id':'m1','start':7,'end':17}]
        clips = [{'id':'c1','media_id':'m1','start':0,'end':13,'enabled':True},
                 {'id':'c2','media_id':'m1','start':0,'end':6,'enabled':True}]
        self.assertEqual(evaluate_quality(refs,clips)['matched'],2)


class QualityProjectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app = Studio(Path(self.tmp.name) / 'workspace')
        self.app.project['files'] = [
            {'id':'m1','name':'capture.mp4','duration':100,'size':1000,
             'analysis':{'audio_levels':[],'motion_levels':[],'transcript':[]},
             'analyzed':True,'analysis_signature':self.app.analysis_signature()}
        ]
        self.app.project['clips'] = [
            {'id':'c1','media_id':'m1','source_name':'capture.mp4',
             'start':10,'end':20,'score':90,'label':'Test','enabled':True}
        ]
        self.app._save()

    def test_reference_annotations_persist_without_mutating_draft(self):
        before_clips = copy.deepcopy(self.app.project['clips'])
        before_analysis = copy.deepcopy(self.app.project['files'][0]['analysis'])
        reference = self.app.add_quality_reference('m1',10,20,'Реакция')
        self.assertEqual(self.app.project['clips'], before_clips)
        self.assertEqual(self.app.project['files'][0]['analysis'],before_analysis)
        reopened = Studio(self.app.work_dir)
        self.assertEqual(reopened.project['quality_references'], [reference])
        report = reopened.quality_report()
        self.assertTrue(report['ready'])
        self.assertEqual(report['f1'],1.0)
        reopened.remove_quality_reference(reference['id'])
        self.assertEqual(Studio(self.app.work_dir).project.get('quality_references'), [])

    def test_invalid_reference_rejected_and_no_state_changed(self):
        for start,end in [(-1,3),(3,101),(5,5),('nan',7),('inf',9),('bad',3),(5,4)]:
            with self.subTest(start=start,end=end):
                with self.assertRaises(ValueError):
                    self.app.add_quality_reference('m1',start,end)
        with self.assertRaises(ValueError):
            self.app.add_quality_reference('not-found',2,5)
        self.assertFalse(self.app.project.get('quality_references'))

    def test_reference_does_not_allow_duplicate_or_unbounded_labels(self):
        self.app.add_quality_reference('m1',10,20,'one')
        with self.assertRaises(ValueError):
            self.app.add_quality_reference('m1',10,20,'duplicate')
        with self.assertRaises(ValueError):
            self.app.add_quality_reference('m1',10,22,'a'*501)
        self.assertEqual(len(self.app.project['quality_references']), 1)

    def test_rescan_invalidates_annotation_only_for_changed_recording(self):
        root = Path(self.tmp.name) / 'captures'
        root.mkdir()
        a, b = root/'a.mp4', root/'b.mp4'
        a.write_bytes(b'a'*10)
        b.write_bytes(b'b'*20)
        self.app.configure(str(root),{'whisper':False,'vision':False})
        with patch('engine.probe', return_value={'duration':30.0,'width':1920,'height':1080,'audio':False}):
            self.app.scan()
        entries = {f['name']: f for f in self.app.project['files']}
        keep = self.app.add_quality_reference(entries['b.mp4']['id'],3,6)
        self.app.add_quality_reference(entries['a.mp4']['id'],1,5)
        a.write_bytes(b'a'*25)
        with patch('engine.probe', return_value={'duration':30.0,'width':1920,'height':1080,'audio':False}):
            self.app.scan()
        self.assertEqual(self.app.project['quality_references'], [keep])

    def test_reference_edit_invalidates_existing_plan_preview(self):
        candidates = [{'start':12.,'end':32.,'score':81.,'label':'Interesting reaction and dialogue',
                       'type':'dialogue'}]
        with patch('engine.generate_candidates',return_value=candidates):
            preview = self.app.preview_plans(0.5)
        self.app.add_quality_reference('m1',12,32)
        with self.assertRaisesRegex(ValueError,'устарел'):
            self.app.apply_plan_variant(preview['token'],'balanced')

    def test_source_change_clears_annotations(self):
        self.app.add_quality_reference('m1',5,12)
        folder=Path(self.tmp.name)/'other'
        folder.mkdir()
        self.app.configure(str(folder))
        self.assertEqual(self.app.project['quality_references'],[])

    def test_preview_variants_report_quality_but_do_not_save_or_apply(self):
        self.app.add_quality_reference('m1',12,32)
        before = self.app.meta.read_bytes()
        candidates = [
            {'start':12.,'end':32.,'score':82.,'label':'Полноценный игровой диалог и реакция',
             'type':'dialogue','reasons':['реакция']},
            {'start':45.,'end':60.,'score':68.,'label':'Шум выстрелов',
             'type':'reaction','reasons':['звук']},
        ]
        with patch('engine.generate_candidates',return_value=candidates):
            result = self.app.preview_plans(0.5)
        self.assertEqual(self.app.meta.read_bytes(), before)
        self.assertEqual(len(self.app.project['clips']),1)
        for variant in result['variants'].values():
            self.assertIn('quality',variant)
            self.assertTrue(variant['quality']['ready'])

    def test_local_api_reference_and_evaluation(self):
        import server
        previous = server.studio
        server.studio = self.app
        http = ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        worker = threading.Thread(target=http.serve_forever,daemon=True)
        worker.start()
        def post(name,payload):
            req=Request(f'http://127.0.0.1:{http.server_port}/api/{name}',
                        data=json.dumps(payload).encode('utf-8'),
                        headers={'Content-Type':'application/json'},method='POST')
            with urlopen(req,timeout=4) as response:
                return json.load(response)
        try:
            reference=post('quality-reference-add',{'media_id':'m1','start':10,'end':20,'label':'Manually verified'})
            with urlopen(f'http://127.0.0.1:{http.server_port}/api/quality-report',timeout=4) as response:
                report=json.load(response)
            self.assertEqual(report['f1'],1.0)
            with urlopen(f'http://127.0.0.1:{http.server_port}/api/status',timeout=4) as response:
                status=json.load(response)
            self.assertEqual(len(status['quality_references']),1)
            post('quality-reference-remove',{'id':reference['id']})
            self.assertEqual(self.app.project['quality_references'],[])
        finally:
            http.shutdown()
            http.server_close()
            worker.join(timeout=4)
            server.studio=previous

if __name__ == '__main__':
    unittest.main()
