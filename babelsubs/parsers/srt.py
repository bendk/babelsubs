import re

from lxml import etree
from babelsubs import utils
from babelsubs.parsers.base import BaseTextParser, register

class SRTParser(BaseTextParser):

    file_type = 'srt'
    _clean_pattern = re.compile(r'\{.*?\}', re.DOTALL)

    def __init__(self, input_string, language_code):
        pattern = r'\d+\s*?\n'
        pattern += r'(?P<s_hour>\d{2}):(?P<s_min>\d{2}):(?P<s_sec>\d{2})(,(?P<s_secfr>\d*))?'
        pattern += r' --> '
        pattern += r'(?P<e_hour>\d{2}):(?P<e_min>\d{2}):(?P<e_sec>\d{2})(,(?P<e_secfr>\d*))?'
        pattern += r'\n(\n|(?P<text>.+?)\n\n)'
        self.language_code = language_code
        self._pattern = re.compile(pattern, re.DOTALL)

        #replace \r\n to \n and fix end of last subtitle
        self.input_string = input_string.replace('\r\n', '\n')+'\n\n'
        self.language = language_code

    def _get_time(self, hour, min, sec, secfr):
        if secfr is None:
            secfr = '0'
        res  =  (int(hour)*60*60+int(min)*60+int(sec)+float('.'+secfr)) * 1000
        return res

    def _get_data(self, match):
        output = {}
        output['start'] = self._get_time(match['s_hour'], match['s_min'], match['s_sec'], match['s_secfr'])
        output['end'] = self._get_time(match['e_hour'], match['e_min'], match['e_sec'], match['e_secfr'])
        output['text'] = '' if match['text'] is None else \
            utils.strip_tags(self._clean_pattern.sub('', match['text']))
        return output

    def get_markup(self, text):
        # create a simple element so we can parse using etree
        # since srt uses html like tags as markup
        base = "<p>%s</p>" % text
        el = etree.fromstring(base)

        content = [el.text]
        base_span = '<span %s>%s</span>'

        for child in el.getchildren():
            tag = child.tag

            if tag == 'b':
                content.append(base_span % ('fontWeight="bold"', child.text))
            elif tag == 'i':
                content.append(base_span % ('fontStyle="italic"', child.text))
            elif tag == 'u':
                content.append(base_span % ('textDecoration="underline"', child.text))

            content.append(child.tail)

        if el.tail:
            content.append(el.tail.strip())
            
        return "".join(filter(None, content)).replace("\n", "<br />")

register(SRTParser)
