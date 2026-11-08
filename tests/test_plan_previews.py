"""Regression tests for safe, reversible CLIPTORA plan previews."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from engine import Studio


class PreviewTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)/'work'
        self.app = Studio(self.folder)
        self.app.project['files']=[{'id':'video','name':'video.mp4','duration':150,
             'analysis':{'audio_levels':[],'motion_levels':[],'transcript':[]},
             'analyzed':True,'analysis_signature':self.app.analysis_signature()}]
        self.manual = {'id':'manual-1','media_id':'video','source_name':'video.mp4',
                       'start':1.,'end':7.,'score':100,'type':'manual',
                       'label':'ручная правка','enabled':False,'zoom':True}
        self.app.project['clips']=[copy.deepcopy(self.manual)]
        self.app._save()
        self.candidates=[
            {'start':10.,'end':30.,'score':81,'label':'Подожди там кто-то идёт сюда и что теперь делать','type':'dialogue','reasons':['сохранена подводка']},
            {'start':34.,'end':54.,'score':82,'label':'сильный игровой звук','type':'reaction','reasons':[]},
            {'start':59.,'end':79.,'score':78,'label':'динамика игры','type':'motion','reasons':[]}
        ]

    def preview(self):
        with patch('engine.generate_candidates',return_value=copy.deepcopy(self.candidates)):
            return self.app.preview_plans(.5)

    def test_preview_does_not_write_project(self):
        before=self.app.meta.read_bytes()
        preview=self.preview()
        self.assertEqual(self.app.meta.read_bytes(),before)
        self.assertEqual(self.app.project['clips'],[self.manual])
        self.assertEqual(set(preview['variants']),{'balanced','dialogue','action'})
        self.assertTrue(preview['variants']['dialogue']['clips'])

    def test_variants_have_distinct_preferences(self):
        previews=self.preview()['variants']
        self.assertNotEqual([x['start'] for x in previews['dialogue']['clips']],
                            [x['start'] for x in previews['action']['clips']])

    def test_apply_undo_recovers_disabled_manual_clip_after_restart(self):
        preview=self.preview()
        self.app.apply_plan_variant(preview['token'],'dialogue')
        self.assertNotEqual(self.app.project['clips'],[self.manual])
        self.assertTrue(self.app.status()['plan_undo_available'])
        restarted=Studio(self.folder)
        self.assertEqual(restarted.undo_plan(),[self.manual])
        self.assertEqual(Studio(self.folder).project['clips'],[self.manual])

    def test_stale_token_and_unknown_variant_do_not_overwrite(self):
        preview=self.preview()
        with self.assertRaises(ValueError):
            self.app.apply_plan_variant('wrong','balanced')
        with self.assertRaises(ValueError):
            self.app.apply_plan_variant(preview['token'],'../../bad')
        self.app.edit_clip('manual-1',label='updated')
        with self.assertRaisesRegex(ValueError,'устарел'):
            self.app.apply_plan_variant(preview['token'],'balanced')
        self.assertEqual(self.app.project['clips'][0]['label'],'updated')

    def test_rejects_invalid_duration_and_missing_source_on_undo(self):
        for x in (0,-1,float('nan'),'broken'):
            with self.assertRaises(ValueError):
                self.app.preview_plans(x)
        preview=self.preview()
        self.app.apply_plan_variant(preview['token'],'balanced')
        current=copy.deepcopy(self.app.project['clips'])
        self.app.project['files']=[]
        self.app._save()
        with self.assertRaises(ValueError):
            self.app.undo_plan()
        self.assertEqual(self.app.project['clips'],current)


if __name__ == '__main__':
    unittest.main()
