# -*- coding: utf-8 -*-

import unittest

from genshi.builder import tag

from trac.core import Component, implements
from trac.notification import IEmailSender
from trac.test import EnvironmentStub
from trac.ticket.model import Ticket
from trac.web.api import ITemplateStreamFilter

from trachtmlnotification.notification import HtmlNotificationModule

message = """\
From: <trac@localhost>
To: <trac@localhost>
X-Trac-Ticket-URL: %(url)s
Content-Type: text/plain; charset=utf-8

email body
"""


class FilterStreamComponent(Component):

    implements(ITemplateStreamFilter)

    def filter_stream(self, req, method, filename, stream, data):
        req.method
        req.path_info
        req.query_string
        def filter(stream, ctxt=None):
            for event in stream:
                yield event
            for event in tag.script('// BLAH-BLAH-BLAH'):
                yield event
        return stream | filter


class NormalTestCase(unittest.TestCase):

    def setUp(self):
        self.env = EnvironmentStub(default_data=True,
                                   enable=['trac.*', 'trachtmlnotification.*'])
        self.env.config.set('notification', 'mime_encoding', 'none')
        self.mod = HtmlNotificationModule(self.env)

    def tearDown(self):
        self.env.reset_db()

    def test_newticket(self):
        ticket = Ticket(self.env)
        ticket['status'] = 'new'
        ticket['summary'] = 'Blah blah blah'
        ticket['reporter'] = 'joe'
        ticket['description'] = '<<<Description>>>'
        ticket.insert()
        orig = message % {'url': 'http://localhost/ticket/%d' % ticket.id}
        result = self.mod.substitute_message(orig, ignore_exc=False)
        self.assertNotEqual(result, orig)
        self.assertTrue('\nContent-Type: text/html;' in result)
        self.assertTrue('&lt;&lt;&lt;Description&gt;&gt;&gt;' in result)

    def test_ticket_comment(self):
        ticket = Ticket(self.env)
        ticket['status'] = 'new'
        ticket['summary'] = 'Blah blah blah'
        ticket['reporter'] = 'joe'
        ticket['description'] = '`<<<Description>>>`'
        ticket.insert()
        ticket.save_changes(author='anonymous', comment='`>>>first comment<<<`')
        ticket.save_changes(author='anonymous', comment='`>>>second comment<<<`')
        url = 'http://localhost/ticket/%d#comment:2' % ticket.id
        orig = message % {'url': url}
        result = self.mod.substitute_message(orig, ignore_exc=False)
        self.assertNotEqual(result, orig)
        self.assertTrue('\nContent-Type: text/html;' in result)
        self.assertTrue('&lt;&lt;&lt;Description&gt;&gt;&gt;' in result)
        self.assertFalse('&gt;&gt;&gt;first comment&lt;&lt;&lt;' in result)
        self.assertTrue('&gt;&gt;&gt;second comment&lt;&lt;&lt;' in result)


class RequestAttributeTestCase(unittest.TestCase):

    def setUp(self):
        self.env = EnvironmentStub(
            default_data=True,
            enable=['trac.*', 'trachtmlnotification.*',
                    'trachtmlnotification.tests.*'])
        self.env.config.set('notification', 'mime_encoding', 'none')
        self.mod = HtmlNotificationModule(self.env)

    def tearDown(self):
        self.env.reset_db()

    def test_read_attribute_in_filter_stream(self):
        ticket = Ticket(self.env)
        ticket['status'] = 'new'
        ticket['summary'] = 'Blah blah blah'
        ticket['reporter'] = 'joe'
        ticket['description'] = '<<<Description>>>'
        ticket.insert()
        orig = message % {'url': 'http://localhost/ticket/%d' % ticket.id}
        result = self.mod.substitute_message(orig, ignore_exc=False)
        self.assertNotEqual(result, orig)
        self.assertTrue('\nContent-Type: text/html;' in result)
        self.assertTrue('<script>// BLAH-BLAH-BLAH</script>' in result)


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(NormalTestCase))
    suite.addTest(unittest.makeSuite(RequestAttributeTestCase))
    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
