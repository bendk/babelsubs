# -*- coding: utf-8 -*-
# Amara, universalsubtitles.org
#
# Copyright (C) 2012 Participatory Culture Foundation
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License along
# with this program.  If not, see http://www.gnu.org/licenses/agpl-3.0.html.

from itertools import izip_longest
import os
import re
from lxml import etree
from xml.sax.saxutils import escape as escape_xml
from collections import namedtuple

from babelsubs import utils

SCHEMA_PATH =  os.path.join(os.getcwd(), "data", 'xsdchema', 'all.xsd')
#schema = lxml.etree.XMLSchema(lxml.etree.parse(open(SCHEMA_PATH)))

TIME_EXPRESSION_METRIC = re.compile(r'(?P<num>[\d]{1,})(?P<unit>(h|ms|s|m|f|t))')
TIME_EXPRESSION_CLOCK_TIME = re.compile(r'(?P<hours>[\d]{2,3}):(?P<minutes>[\d]{2}):(?P<seconds>[\d]{2})(?:.(?P<fraction>[\d]{1,3}))?')

NEW_PARAGRAPH_META_KEY = 'new_paragraph'
TTML_NAMESPACE_URI = 'http://www.w3.org/ns/ttml'

SubtitleLine = namedtuple("SubtitleLine", ['start_time', 'end_time', 'text', 'meta'])

def get_attr(el, attr):
    """Get the string of an attribute, or None if it's not present.

    Ignores namespaces to save your sanity.

    """
    for k, v in el.attrib.items():
        if k == attr or k.rsplit('}', 1)[-1] == attr:
            return v

def get_contents(el):
    """Get the contents of the given element as a string of XML.

    Based on
    http://stackoverflow.com/questions/4624062/get-all-text-inside-a-tag-in-lxml
    but edited to actually work.

    I cannot believe this is not part of lxml.  Seriously, what are they
    thinking?  This is one of the most basic things people would need.

    """
    parts = ([el.text] +
             list(''.join(filter(None, [c.text, c.tail])) for c in el.getchildren()) +
             [el.tail])
    return ''.join(filter(None, parts)).strip()

def time_expression_to_milliseconds(time_expression, tick_rate=None):
    """
    Parses possible values from time expressions[1] to a normalized value
    in milliseconds.

    We don't support all possible forms now, only clock time, metric and tick.
    [1] http://www.w3.org/TR/ttaf1-dfxp/#timing-value-timeExpression
    """
    if not time_expression:
        return 0
    match = TIME_EXPRESSION_CLOCK_TIME.match(time_expression)
    if match:
        groups = match.groupdict()
        hour = int(groups['hours'])
        minutes = int(groups['minutes'])
        seconds  = int(groups['seconds'])
        milliseconds = int(groups['fraction'] or 0)
        return (((hour * 3600) + (minutes * 60) + seconds ) * 1000 ) + milliseconds
    match = TIME_EXPRESSION_METRIC.match(time_expression)
    if match:
        groups = match.groupdict()
        num, unit = int(groups['num']), groups['unit']
        if unit == 't':
            if not tick_rate:
                raise ValueError("Ticks need a tick rate, mate.")
            return 1000 * (num / float(tick_rate))
        multiplier = {
            "h": 3600 * 1000,
            "m": 60 * 1000,
            "s": 1000,
            "ms": 1,
            'f': 0,
        }.get(unit, None)
        return num * multiplier
    raise ValueError("Time expression %s can't be parsed" % time_expression)


def milliseconds_to_time_clock_exp(milliseconds):
    """
    Converts time components to a string suitable to be used on time expression
    fot ttml
    """
    if milliseconds is None:
        return None
    expression = '%(hours)02d:%(minutes)02d:%(seconds)02d.%(milliseconds)03d'
    return expression % utils.milliseconds_to_time_clock_components(milliseconds)

def to_clock_time(time_expression, tick_rate=None):
    """
    If time expression is not in clock time, transform it
    """
    match = TIME_EXPRESSION_CLOCK_TIME.match(time_expression)
    if match:
        return time_expression
    return milliseconds_to_time_clock_exp(time_expression_to_milliseconds(time_expression, tick_rate))

def diff(set_1, set_2):
    """
    Performs a simple diff, only taking into account:
    - Start and end time
    - Text

    The returned data structure looks like this:
    {
        changed : bool (true if either text_changed or time_changed > 0)
        text_changed: (float between 0 and 1)
        time_changed: (float between 0 and 1)
        subtitle_data: [
            {
                time_changed: bool,
                text_changed: bool,
                subtitle_1: [the subtitle data, (start_time, end_time, text),
                subtitle_2: [the subtitle data, (start_time, end_time, text),
            }, ... ordered list with both subtitles. If one list is longer , you
            will get an empty SubtitleLine named tupple
        ]
    """
    result = {
        'subtitle_data' : [],
        'changed': False,
        'text_changed': 0,
        'time_changed': 0,
        }
    text_change_count = 0
    time_change_count = 0
    if len(set_1) == 0 and len(set_2) == 0:
        # empty sets are the same
        return result
    for sub_1, sub_2 in izip_longest([x for x in set_1.subtitle_items()],
                                       [x for x in set_2.subtitle_items()]):
        sub_1 = sub_1 or SubtitleLine(None, None, None, None)
        sub_2 = sub_2 or SubtitleLine(None, None, None, None)
        subtitle_result  = {
            'time_changed': False,
            'text_changed': False,
            'subtitles' : [sub_1, sub_2]
        }
        subtitle_result['time_changed'] = sub_1.start_time != sub_2.start_time or sub_1.end_time != sub_2.end_time
        if subtitle_result['time_changed']:
            time_change_count +=1
        subtitle_result['text_changed']  = sub_1.text != sub_2.text
        if subtitle_result['text_changed']:
            text_change_count +=1
        result['subtitle_data'].append(subtitle_result)
    longest_set_count = max(len(set_1),len(set_2))
    result['text_changed'] = text_change_count / (longest_set_count * 1.0)
    result['time_changed'] = time_change_count / (longest_set_count * 1.0)
    result['changed'] = (time_change_count + text_change_count) > 0
    return result

class SubtitleSet(object):
    BASE_TTML = r'''
        <tt xml:lang="%(language_code)s" xmlns="%(namespace_uri)s">
            <head>
                <metadata xmlns:ttm="http://www.w3.org/ns/ttml#metadata">
                    <ttm:title>%(title)s</ttm:title>
                    <ttm:description>%(description)s</ttm:description>
                    <ttm:copyright></ttm:copyright>
                </metadata>

                <styling xmlns:tts="http://www.w3.org/ns/ttml#styling">
                    <style xml:id="amara-style"
                        tts:color="white"
                        tts:fontFamily="proportionalSansSerif"
                        tts:fontSize="18px"
                        tts:textAlign="center"
                    />
                </styling>

                <layout xmlns:tts="http://www.w3.org/ns/ttml#styling">
                    <region xml:id="amara-subtitle-area"
                            style="amara-style"
                            tts:extent="560px 62px"
                            tts:padding="5px 3px"
                            tts:backgroundColor="black"
                            tts:displayAlign="after"
                    />
                </layout>
            </head>
            <body region="amara-subtitle-area">
                <div>
                </div>
            </body>
        </tt>
    '''

    SUBTITLE_XML = r'''<p xmlns="http://www.w3.org/ns/ttml" %s %s>%s</p>'''

    SUBTITLE_DIV_XML = r'''<div xmlns="http://www.w3.org/ns/ttml"></div>'''
    
    def __init__(self, language_code, initial_data=None, title=None,
                 description=None, normalize_time=True):
        """Create a new set of Subtitles, either empty or from a hunk of TTML.

        language_code: The bcp47 code for this language.
        initial_data: any optional xml as the starting point.
        NO UNICODE ALLOWED!  USE XML ENTITIES TO REPRESENT UNICODE CHARACTERS!

        """
        if initial_data:
            self._ttml = etree.fromstring(initial_data)
            self.tick_rate = self._get_tick_rate()
            if normalize_time:
                [self.normalize_time(x) for x in self.get_subtitles()]
        else:
            self._ttml = etree.fromstring(SubtitleSet.BASE_TTML % {
                'namespace_uri': TTML_NAMESPACE_URI,
                'title' : title or '',
                'description': description or '',
                'language_code': language_code or '',
            })

        self.subtitles = self.subtitle_items()

    def __len__(self):
        return len(self.get_subtitles())

    def __getitem__(self, key):
        return self.subtitles[key]

    def get_subtitles(self):
        divs = self._ttml.xpath('/n:tt/n:body/n:div', namespaces={'n': TTML_NAMESPACE_URI})
        result = []

        for div in divs:
            el_count = 0

            for el in div.xpath('n:p', namespaces={'n': TTML_NAMESPACE_URI}):
                if el_count == 0:
                    el.attrib[NEW_PARAGRAPH_META_KEY] = 'true'
                el_count += 1
                result.append(el)

        return result

    def append_subtitle(self, from_ms, to_ms, content, new_paragraph=False,
                        escape=True):
        """Append a subtitle to the end of the list.

        NO UNICODE ALLOWED!  USE XML ENTITIES TO REPRESENT UNICODE CHARACTERS!

        """
        
        begin_value = milliseconds_to_time_clock_exp(from_ms)
        begin = 'begin="%s"' % begin_value if begin_value else ''
        end_value = milliseconds_to_time_clock_exp(to_ms)
        end = 'end="%s"' %  end_value if end_value else ''

        if escape:
            content = escape_xml(content)
        p = etree.fromstring(SubtitleSet.SUBTITLE_XML % (begin, end, content))
        div = self._ttml.xpath('/n:tt/n:body/n:div',
                               namespaces={'n': TTML_NAMESPACE_URI})[-1]
        if new_paragraph:
            body = self._ttml.xpath('/n:tt/n:body',
                                   namespaces={'n': TTML_NAMESPACE_URI})[-1]
            div = etree.fromstring(SubtitleSet.SUBTITLE_DIV_XML)
            body.append(div)
        div.append(p)

    def normalize_time(self, el):
        """
        Transforms begin,dur pairs into begin,end pairs
        also uses clock time expressions (00:00:00).

        Changes node in place
        """
        begin = get_attr(el, 'begin')
        if begin:
            begin = to_clock_time(begin, self.tick_rate)
        end = get_attr(el, 'end')
        if end:
            end = to_clock_time(end, self.tick_rate)
        dur = get_attr(el, 'dur')
        if dur :
            end= milliseconds_to_time_clock_exp(
                time_expression_to_milliseconds(begin, self.tick_rate) + \
                time_expression_to_milliseconds(dur, self.tick_rate))
            el.attrib.pop('dur')
        if begin:
            el.attrib['begin'] = begin
        if end:
            el.attrib['end'] = end

    def subtitle_items(self, mappings=None):
        """
        Return a list of (from_ms, to_ms, content, meta) tuples.

        The from and to millisecond values may be any time expression
        that we can parse.

        Meta is a dict with additional information.
        """
        result = []

        for el in self.get_subtitles():
            meta = {
                NEW_PARAGRAPH_META_KEY: el.attrib.get(NEW_PARAGRAPH_META_KEY,
                    'false')
            }
            result.append(self._extract_from_el(el, meta, mappings))

        self.subtitles = result
        return result

    def _extract_from_el(self, el, meta, mappings):
        begin = get_attr(el, 'begin')
        end = get_attr(el, 'end')

        from_ms = (time_expression_to_milliseconds(begin)
                if begin else None)
        to_ms = (time_expression_to_milliseconds(end)
                if end else None)

        if not mappings:
            content = get_contents(el)
        else:
            content = self.get_content_with_markup(el, mappings).strip()

        return SubtitleLine(from_ms, to_ms, content, meta)

    def __clear_namespace(self, name):
        return name.split("}")[-1] if '}' in name else name

    def item_is_synced(self, el):
        return 'begin' in el.attrib and 'end' in el.attrib

    @property
    def fully_synced(self):
        for item in self.get_subtitles():
            if not self.item_is_synced(item):
                return False
        return True

    def get_content_with_markup(self, el, mappings):
        text = [el.text]
        for child in el.getchildren():
            # no i don't want  to deal with namespaces right now sorry
            attrs = dict([(self.__clear_namespace(n), v) for n, v in child.items()])

            tag = self.__clear_namespace(child.tag)

            if tag == 'span':
                value = "%s"

                if attrs.get('fontWeight', '') == 'bold' and 'bold' in mappings:
                    value = value % mappings.get("bold", "")

                if attrs.get('fontStyle', '') == 'italic' and 'italics' in mappings:
                    value = value % mappings.get("italics", "")

                if attrs.get('textDecoration', '') == 'underline' and 'underline' in mappings:
                    value = value % mappings.get("underline", "")

                text.append(value % child.text)

            if tag == "br":
                text.append(mappings.get("linebreaks", ""))

            if child.tail:
                text.append(child.tail)

        if el.tail:
            text.append(el.tail)

        return ''.join(filter(None, text))


    @classmethod
    def from_list(cls, language_code, subtitles, escape=False):
        """Return a SubtitleSet from a list of subtitle tuples.

        Each tuple should be (from_ms, to_ms, content).  See the docstring of
        append_subtitle for more information.

        For example:

            [(0, 1000, "Hello, "),
             (1100, None, "world!")]

        """
        subs = SubtitleSet(language_code=language_code)

        for s in subtitles:
            subs.append_subtitle( *s, **{'escape':escape})

        return subs

    def _get_tick_rate(self):
        tt = self._ttml.xpath('/n:tt', namespaces={'n': TTML_NAMESPACE_URI})[0] 
        for name,value in tt.attrib.items():
            if name == "tickRate":
                return int(value)
        return 1
 
    def __eq__(self, other):
        if type(self) == type(other):
            return self.to_xml() == other.to_xml()
        else:
            return False

    def __nonzero__(self):
        return bool(self.__len__())

    def validate(self):
        raise NotImplementedError("Validation isnt working so far")

    def to_xml(self):
        return etree.tostring(self._ttml, pretty_print=True)
