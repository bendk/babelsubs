from unittest2 import TestCase
from babelsubs.storage import SubtitleSet, SubtitleLine, diff

class DiffingTest(TestCase):
    def test_empty_subs(self):
        result = diff(SubtitleSet('en'), SubtitleSet('en'))
        self.assertEqual(result['changed'], False)
        self.assertEqual(result['text_changed'], 0)
        self.assertEqual(result['time_changed'], 0)
        self.assertEqual(len(result['subtitle_data']), 0)


    def test_one_set_empty(self):
        set_1 = SubtitleSet.from_list('en', [
            (0, 1000, "Hey 1"),
            (1000, 2000, "Hey 2"),
            (2000, 3000, "Hey 3"),
            (3000, 4000, "Hey 4"),
        ])
        result = diff(set_1, SubtitleSet('en'))
        self.assertEqual(result['changed'], True)
        self.assertEqual(result['text_changed'], 1.0)
        self.assertEqual(result['time_changed'], 1.0)

    def test_text_changes(self):
        set_1 = SubtitleSet.from_list('en', [
            (0, 1000, "Hey 1"),
            (1000, 2000, "Hey 2"),
            (2000, 3000, "Hey 3"),
            (3000, 4000, "Hey 4"),
            ])
        set_2 = SubtitleSet.from_list('en', [
            (0, 1000, "Hey 1"),
            (1000, 2000, "Hey 22"),
            (2000, 3000, "Hey 3"),
            (3000, 4000, "Hey 4"),
            ])
        result = diff(set_1, set_2)
        self.assertEqual(result['changed'], True)
        self.assertEqual(result['text_changed'], 1/4.0)
        self.assertEqual(result['time_changed'], 0)
        self.assertEqual(len(result['subtitle_data']), 4)
        # only sub #2 should have text changed
        for i,sub_data in enumerate(result['subtitle_data']):
            self.assertEqual(sub_data['text_changed'], i ==1)

    def test_time_changes(self):
        set_1 = SubtitleSet.from_list('en', [
         (0, 1000, "Hey 1"),
         (1000, 2000, "Hey 2"),
         (2000, 3000, "Hey 3"),
         (3000, 4000, "Hey 4"),
        ])
        set_2 = SubtitleSet.from_list('en', [
         (0, 1000, "Hey 1"),
         (1200, 2000, "Hey 2"),
         (2000, 3000, "Hey 3"),
         (3000, 4000, "Hey 4"),
        ])
        result = diff(set_1, set_2)
        self.assertEqual(result['changed'], True)
        self.assertEqual(result['time_changed'], 1/4.0)
        self.assertEqual(result['text_changed'], 0)
        self.assertEqual(len(result['subtitle_data']), 4)
        # only sub #2 should have text changed
        for i,sub_data in enumerate(result['subtitle_data']):
            self.assertEqual(sub_data['time_changed'], i ==1)
            self.assertFalse(sub_data['text_changed'])

    def test_insert(self):
        set_1 = SubtitleSet.from_list('en', [
         (0, 1000, "Hey 1"),
         (1000, 2000, "Hey 2"),
         (2000, 3000, "Hey 3"),
         (3000, 4000, "Hey 4"),
        ])
        set_2 = SubtitleSet.from_list('en', [
         (0, 1000, "Hey 1"),
         (500, 800, "Hey 1.5"),
         (1000, 2000, "Hey 2"),
         (2000, 3000, "Hey 3"),
         (3000, 4000, "Hey 4"),
        ])
        result = diff(set_1, set_2)
        self.assertEqual(result['changed'], True)
        # for both time_change and text_changed, we calculate them as follows:
        # there are 9 total subs (4 in set_1, 5 in set_2).  8 of those are
        # matches and 1 is new in set_2.  So the change amount is 1/9
        self.assertAlmostEqual(result['time_changed'], 1/9.0)
        self.assertAlmostEqual(result['text_changed'], 1/9.0)
        self.assertEqual(len(result['subtitle_data']), 5)

        # check the lines that haven't changed
        for i in (0, 2, 3, 4):
            sub_data = result['subtitle_data'][i]
            self.assertEquals(sub_data['time_changed'], False)
            self.assertEquals(sub_data['text_changed'], False)
            self.assertEquals(sub_data['subtitles'][0], set_2[i])
            self.assertEquals(sub_data['subtitles'][1], set_2[i])
        # check the line that was inserted
        insert_sub_data = result['subtitle_data'][1]
        self.assertEquals(insert_sub_data['time_changed'], True)
        self.assertEquals(insert_sub_data['text_changed'], True)
        self.assertEquals(insert_sub_data['subtitles'][0],
                          SubtitleLine(None, None, None, None))
        self.assertEquals(insert_sub_data['subtitles'][1], set_2[1])

    def test_data_ordering(self):
        set_1 = SubtitleSet.from_list('en', [
            (0, 1000, "Hey 1"),
        ])
        set_2 = SubtitleSet.from_list('en', [
            (0, 1000, "Hey 1"),
            (1200, 2000, "Hey 2"),
            (2000, 3000, "Hey 3"),
        ])
        result = diff(set_1, set_2)

        subs_result = result['subtitle_data'][2]['subtitles']
        # make sure the 0 index subs is for set_1, test
        # we respect the ordering of arguments passed to diff
        self.assertEqual(subs_result[0].text , None)
        self.assertEqual(subs_result[1].text , "Hey 3")

    def test_unsynced_reflect_time_changes(self):
        set_1 = SubtitleSet.from_list('en', [
            (0, 1000, "Hey 1"),
            ])
        set_2 = SubtitleSet.from_list('en', [
            (0, 1000, "Hey 1"),
            (None, None, "Hey 2"),
            ])
        result = diff(set_1, set_2)

        self.assertAlmostEqual(result['time_changed'], 1/3.0)
