# -*- coding: utf-8 -*-

import email
import os.path
import re
from email.MIMEText import MIMEText
from email.MIMEMultipart import MIMEMultipart
from genshi.builder import tag
Locale = None
try:
    from babel.core import Locale
except ImportError:
    pass

from trac.core import Component, implements
from trac.attachment import AttachmentModule
from trac.env import Environment
from trac.mimeview.api import Context
from trac.notification import SmtpEmailSender, SendmailEmailSender
from trac.resource import ResourceNotFound
from trac.test import MockPerm
from trac.ticket.model import Ticket
from trac.ticket.web_ui import TicketModule
from trac.timeline.web_ui import TimelineModule
from trac.util.datefmt import get_timezone, localtz
from trac.util.text import to_unicode
from trac.util.translation import deactivate, make_activable, reactivate, tag_
from trac.web.api import Request
from trac.web.chrome import Chrome, ITemplateProvider
from trac.web.main import FakeSession


_TICKET_URI_RE = re.compile(r'/ticket/(?P<tktid>[0-9]+)'
                            r'(?:#comment:(?P<cnum>[0-9]+))?\Z')


if Locale:
    def _parse_locale(lang):
        try:
            return Locale.parse(lang, sep='-')
        except:
            return Locale('en', 'US')
else:
    def _parse_locale(lang):
        return None


if hasattr(Environment, 'get_read_db'):
    def _get_db(env):
        return env.get_read_db()
else:
    def _get_db(env):
        return env.get_db_cnx()


class HtmlNotificationModule(Component):

    implements(ITemplateProvider)

    def get_htdocs_dirs(self):
        return ()

    def get_templates_dirs(self):
        from pkg_resources import resource_filename
        return [resource_filename(__name__, 'templates')]

    def substitute_message(self, message, ignore_exc=True):
        try:
            chrome = Chrome(self.env)
            req = self._create_request()
            t = deactivate()
            try:
                make_activable(lambda: req.locale, self.env.path)
                return self._substitute_message(chrome, req, message)
            finally:
                reactivate(t)
        except:
            self.log.warn('Caught exception while substituting message',
                          exc_info=True)
            if ignore_exc:
                return message
            raise

    def _create_request(self):
        languages = filter(None, [self.config.get('trac', 'default_language')])
        if languages:
            locale = _parse_locale(languages[0])
        else:
            locale = None
        tzname = self.config.get('trac', 'default_timezone')
        tz = get_timezone(tzname) or localtz
        environ = {'REQUEST_METHOD': 'POST', 'REMOTE_ADDR': '127.0.0.1',
                   'SERVER_NAME': 'localhost', 'SERVER_PORT': '80',
                   'wsgi.url_scheme': 'http',
                   'trac.base_url': self.env.abs_href()}
        if languages:
            environ['HTTP_ACCEPT_LANGUAGE'] = ','.join(languages)
        req = Request(environ, lambda *args, **kwargs: None)
        req.arg_list = ()
        req.args = {}
        req.authname = 'anonymous'
        req.session = FakeSession({'dateinfo': 'absolute'})
        req.perm = MockPerm()
        req.href = req.abs_href
        req.locale = locale
        req.lc_time = locale
        req.tz = tz
        req.chrome = {'notices': [], 'warnings': []}
        return req

    def _substitute_message(self, chrome, req, message):
        parsed = email.message_from_string(message)
        link = parsed.get('X-Trac-Ticket-URL')
        if not link:
            return message
        match = _TICKET_URI_RE.search(link)
        if not match:
            return message
        tktid = match.group('tktid')
        cnum = match.group('cnum')
        if cnum is not None:
            cnum = int(cnum)

        db = _get_db(self.env)
        try:
            ticket = Ticket(self.env, tktid)
        except ResourceNotFound:
            return message

        container = MIMEMultipart('alternative')
        for header, value in parsed.items():
            lower = header.lower()
            if lower in ('content-type', 'content-transfer-encoding'):
                continue
            if lower != 'mime-version':
                container[header] = value
            del parsed[header]
        container.attach(parsed)

        html = self._create_html_body(chrome, req, ticket, cnum, link)
        part = MIMEText(html.encode('utf-8'), 'html')
        self._set_charset(part)
        container.attach(part)

        return container.as_string()

    def _create_html_body(self, chrome, req, ticket, cnum, link):
        tktmod = TicketModule(self.env)
        attmod = AttachmentModule(self.env)
        data = tktmod._prepare_data(req, ticket)
        tktmod._insert_ticket_data(req, ticket, data, req.authname, {})
        data['ticket']['link'] = link
        changes = data.get('changes')
        if cnum is None:
            changes = []
        else:
            changes = [change for change in (changes or [])
                              if change.get('cnum') == cnum]
        data['changes'] = changes
        context = Context.from_request(req, ticket.resource, absurls=True)
        alist = attmod.attachment_data(context)
        alist['can_create'] = False
        data.update({
                'can_append': False,
                'show_editor': False,
                'start_time': ticket['changetime'],
                'context': context,
                'alist': alist,
                'styles': self._get_styles(chrome),
                'link': tag.a(link, href=link),
                'tag_': tag_,
               })
        template = 'htmlnotification_ticket.html'
        # use pretty_dateinfo in TimelineModule
        TimelineModule(self.env).post_process_request(req, template, data,
                                                      None)
        rendered = chrome.render_template(req, template, data, fragment=True)
        return unicode(rendered)

    def _get_styles(self, chrome):
        for provider in chrome.template_providers:
            for prefix, dir in provider.get_htdocs_dirs():
                if prefix != 'common':
                    continue
                url_re = re.compile(r'\burl\([^\]]*\)')
                buf = ['#content > hr { display: none }']
                for name in ('trac.css', 'ticket.css'):
                    f = open(os.path.join(dir, 'css', name))
                    try:
                        lines = f.read().splitlines()
                    finally:
                        f.close()
                    buf.extend(url_re.sub('none', to_unicode(line))
                               for line in lines
                               if not line.startswith('@import'))
                return ('/*<![CDATA[*/\n' +
                        '\n'.join(buf).replace(']]>', ']]]]><![CDATA[>') +
                        '\n/*]]>*/')
        return ''

    def _set_charset(self, mime):
        from email.Charset import Charset, QP, BASE64, SHORTEST
        mime_encoding = self.config.get('notification', 'mime_encoding').lower()

        charset = Charset()
        charset.input_charset = 'utf-8'
        charset.output_charset = 'utf-8'
        charset.input_codec = 'utf-8'
        charset.output_codec = 'utf-8'
        if mime_encoding == 'base64':
            charset.header_encoding = BASE64
            charset.body_encoding = BASE64
        elif mime_encoding in ('qp', 'quoted-printable'):
            charset.header_encoding = QP
            charset.body_encoding = QP
        elif mime_encoding == 'none':
            charset.header_encoding = SHORTEST
            charset.body_encoding = None

        del mime['Content-Transfer-Encoding']
        mime.set_charset(charset)


class HtmlNotificationSmtpEmailSender(SmtpEmailSender):

    def send(self, from_addr, recipients, message):
        mod = HtmlNotificationModule(self.env)
        message = mod.substitute_message(message)
        SmtpEmailSender.send(self, from_addr, recipients, message)


class HtmlNotificationSendmailEmailSender(SendmailEmailSender):

    def send(self, from_addr, recipients, message):
        mod = HtmlNotificationModule(self.env)
        message = mod.substitute_message(message)
        SendmailEmailSender.send(self, from_addr, recipients, message)
