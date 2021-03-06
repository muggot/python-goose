# -*- coding: utf-8 -*-
"""\
This is a python port of "Goose" orignialy licensed to Gravity.com
under one or more contributor license agreements.  See the NOTICE file
distributed with this work for additional information
regarding copyright ownership.

Python port was written by Xavier Grangier for Recrutae

Gravity.com licenses this file
to you under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance
with the License.  You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
from goose.parsers import Parser
from goose.utils import ReplaceSequence
from HTMLParser import HTMLParser
import lxml.html
import re


class DocumentCleaner(object):

    def __init__(self):

        # to remove: navbar, scroll, source, fn
        self.regExRemoveNodes = (
        " side |combx|retweet|fontresize|mediaarticlerelated|menucontainer|navbar"
        "|comment|popularquestions|copyrighttext | sitemap | credit |footnote "
        "|cnn_strycaptiontxt|cnn_html_slideshow|links|meta |scroller|shoutbox|sponsor"
        "|tags|socialnetworking|socialnetworking|cnnstryhghlght|feedbackentry"
        "|cnn_stryspcvbx| inset |pagetools|post-attributes"
        "|welcome_form|contenttools2|the_answers|rating"
        "|communitypromo|runaroundleft| subscribe |vcard|articleheadings|articlead|articleimage|slideshowinlinelarge|article-side-rail"
        "| date | wndate | print |popup|author-dropdown|tools|socialtools"
        "|konafilter|breadcrumbs|wp-caption-text"
        "|legende|ajoutvideo|timestamp|menu|story-feature wide|error"
        )
        self.regExNotRemoveNodes = ("and|no|article|body|column|main|shadow|commented|content|author")
        self.re_todel = re.compile(self.regExRemoveNodes.lower())
        self.re_notdel = re.compile(self.regExNotRemoveNodes.lower())
        self.re_dontconvert = re.compile("gallery|photo|slide|caption")
        self.goodInlineTags = set(['b','strong','em','i','a','img','big','cite','code','q','s','small','strike','sub','tt','u','var'])
        self.bad_tags = set(['script','style','option','iframe','noframe'])
        self.good_tags = set(['p','span','b','h1','h2','h3','h4','h5'])
        self.child_tags = set(['a', 'blockquote', 'dl', 'div', 'img', 'ol', 'p', 'pre', 'table', 'ul'])
        self.parser = HTMLParser()
        

    def clean(self, article):
        docToClean = article.doc
        nodelist = self.getNodesToDelete(docToClean)
        for node in nodelist: Parser.remove(node)

        docToClean = self.removeListsWithLinks(docToClean)
        docToClean = self.convertDivsToParagraphs(docToClean, ('div','dl','article'))
        return docToClean

    def getNodesToDelete(self, doc):
        nodelist = []
        for node in doc:
            if node.tag in self.bad_tags or isinstance(node,lxml.html.HtmlComment) or str(node.tag)[0] == '<':
                nodelist.append(node)
                continue
            if node.tag == 'noscript' and len(node) < 2:
                nodelist.append(node)
                continue
            if node.tag == 'span' and len(node) == 0 and (node.text is None or len(node.text) < 30):
                node.drop_tag()
                continue
            if node.tag == 'div' and doc.tag == 'span': doc.tag = 'div'  # convert span to div
            if node.tag == 'br':  # retain line breaks
                node.tail = u'\ufffc' + node.tail if node.tail is not None else u'\ufffc'
                nodelist.append(node)
                continue
            if node.tag in ['body']:
                nodelist += self.getNodesToDelete(node)
                continue
            ids = ['']
            if 'class' in node.attrib: ids.append(node.attrib['class'])
            if 'id' in node.attrib:    ids.append(node.attrib['id'])
            if 'name' in node.attrib:  ids.append(node.attrib['name'])
            ids.append('')
            ids = ' '.join(ids).lower()
            node.attrib['goose_attributes'] = ids

            if " caption " in ids: 
                nodelist.append(node)
                continue
            if node.tag in self.good_tags and len(node) == 0: continue;  # good top level nodes

            match_obj = self.re_notdel.search(ids)
            good_word = match_obj.group() if match_obj is not None else ''
            match_obj = self.re_todel.search(ids)
            bad_word = match_obj.group() if match_obj is not None else ''
            if len(bad_word) and (not len(good_word) or good_word in bad_word):
                if node.tag != 'nav' or bad_word != 'navbar' or not Parser.getElementsByTag(node,tag='article'):  # bogus article in nav case
                    nodelist.append(node)
                    continue 
            if 'mod-washingtonpostarticletext' in ids: # washingtonpost hack
                self.aggregateBlocks(doc, '.mod-washingtonpostarticletext')
            nodelist += self.getNodesToDelete(node)
        if doc.tag == 'span':
            parent = doc.getparent()
            if parent is not None:
                if parent.tag == 'p' or (len(parent) == 1 and parent.tag in ('div','span')): doc.drop_tag()
                elif 'class' in doc.attrib and ('dropcap' in doc.attrib['class'] or 'drop_cap' in doc.attrib['class']):
                    doc.drop_tag()
        if doc.tag == 'index': doc.drop_tag()
        return nodelist

    def aggregateBlocks(self, doc, selector):
        divs = doc.cssselect(selector)
        if len(divs) <= 1: return
        for i in xrange(1,len(divs)):
            divs[0].append(divs[i])
            divs[i].tail = None
            divs[i].attrib['class'] = '' # drop all attributes

    def removeListsWithLinks(self, doc):
        items=Parser.getElementsByTags(doc, ('ol','ul'))
        for item in items:
            fa = 0
            for li in item:
                if Parser.hasChildTag(li, 'a'):
                    fa += 1
                    if fa > 2:
                        parent = item.getparent()
                        Parser.remove(item)
                        if parent is not None:
                            if len(parent) == 0 or len(Parser.getText(parent).split()) < 4:
                                Parser.remove(parent)
                        break
                else:
                   fa = 0
        items=Parser.getElementsByTag(doc, tag='a')
        for a in items:
                e = a.getparent()
		if e is None: continue
	        text = Parser.getText(e)
		ldels = []
                textcount = 0
		for link in e:
	            ltext = Parser.getText(link)
                    if link.tag != 'a' and len(ltext) <= 2: continue
		    if link.tag != 'a' and len(ltext) > 2:
                        ldels = []
                        break
                    if ltext == '': continue
	            ldel = text.split(ltext,1)
	            ld = ldel[0].strip()
	            ldels.append(ld)
                    if len(ldel) == 1: break
	            text = ldel[1]
	        if len(ldels) == 0 or ldels[0] == ',': continue
	        else:
                    del ldels[0]
                    flag = 0; flag1 = 0; flag2 = 0; flag3 = 0
	            for ldel in ldels:
			if ldel == ldels[0]: flag += 1
                        if len(ldel) > 3 or ',' in ldel: flag1 = 1
			if ldel != '': flag2 = 1
                        if len(ldel) > 1: flag3 = 1
                    if flag2 == 0 and len(ldels) > 1: 
			Parser.remove(e)
			continue
                    if  len(ldels) == 2 and ldels[0] == '|' and ldels[1] == '|': 
			Parser.remove(e)
			continue
                    if  len(ldels) > 3 and flag3 == 0: 
			Parser.remove(e)
			continue
                    if (flag <= 2 and len(ldels) <= 2) or flag1 != 0: 
			continue
		         
	        Parser.remove(e)

        return doc

    def getReplacementNodes(self, div):

        replacementText = []
        nodesToReturn = []
        p = Parser.createElement(tag='p', text='', tail=None)
        last_inline_node = None
        if div.text is not None: 
            div.text = self.parser.unescape(div.text).strip('\t\r\n')
            if len(div.text): replacementText.append(div.text)

        for kid in list(div):
            if kid.tail is not None: kid.tail = self.parser.unescape(kid.tail).strip('\t\r\n')
            if replacementText: 
                text = ''.join(replacementText)
                replacementText = []
                if len(p):  last_inline_node.tail = text
                else: p.text = text
            if kid.tag in self.goodInlineTags:
                p.append(kid)
                last_inline_node = kid
            else:
                if len(p) or len(p.text):
                    nodesToReturn.append(p)
                    p = Parser.createElement(tag='p', text='', tail=None)
                if kid.tail is not None and len(kid.tail): replacementText.append(kid.tail)
                kid.tail = None
                nodesToReturn.append(kid)

        # flush out anything still remaining
        if replacementText:
            text = ''.join(replacementText)
            if len(p):  last_inline_node.tail = text
            else: p.text = text
        if len(p) or len(p.text): nodesToReturn.append(p)

        return nodesToReturn

    def convertDivsToParagraphs(self, doc, domTypes):
        divs = Parser.getElementsByTags(doc, domTypes)
        tags = self.child_tags

        for div in divs:
            if div is None: continue
            attrs = div.attrib['goose_attributes'] if 'goose_attributes' in div.attrib else ''
            if not Parser.hasChildTags(div, tags): div.tag = 'p'
            elif self.re_dontconvert.search(attrs) is not None: continue
            else:
                replaceNodes = self.getReplacementNodes(div)
                text = div.tail
                attrib = {}
                for a in div.attrib: attrib[a] = div.attrib[a]
                div.clear()
                div.extend(replaceNodes)
                div.tail = text
                for a in attrib: div.attrib[a] = attrib[a]

        return doc


class StandardDocumentCleaner(DocumentCleaner):
    pass
