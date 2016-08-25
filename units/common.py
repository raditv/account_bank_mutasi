import traceback
import urllib
import mechanize
from StringIO import StringIO
from datetime import (
    date,
    datetime,
    )
from sgmllib import SGMLParser


USER_AGENT_DESKTOP = 'Mozilla/5.0 (X11; Linux x86_64; rv:14.0) Gecko/20100101 Firefox/14.0'
USER_AGENT_MOBILE = 'Mozilla/5.0 (Linux; U; Android 2.3.7; in-id; HTC Wildfire Build/GRI40; CyanogenMod-7) AppleWebKit/533.1 (KHTML, like Gecko) Version/4.0 Mobile Safari/533.1'


class BaseBrowser(object):
    def __init__(self, base_url, username, password, parser=None,
                 user_agent=USER_AGENT_DESKTOP, output_file=None):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.parser = parser 
        self.br = mechanize.Browser()
        self.br.addheaders = [('User-Agent', user_agent)]
        self.br.set_handle_robots(False)
        self.last_error = None
        self.output_file = output_file

    def open_url(self, url=None, POST_data=None, GET_data={}):
        url = self.get_url(url, GET_data)
        if POST_data is not None:
            POST_data = urllib.urlencode(POST_data)
            self.info('POST %s' % url)
        else:
            self.info('GET %s' % url)
        return self.br.open(url, POST_data)

    def get_url(self, url=None, p={}):
        if not url:
            url = self.base_url
        elif url[0] == '/':
            url = self.base_url + url
        if p:
            url = '?'.join([url, dict2url(p)])
        return url

    def get_content(self, url=None, POST_data=None, GET_data={}):
        resp = self.open_url(url, POST_data, GET_data)
        return resp.read()

    def login(self):
        pass

    def logout(self):
        pass

    def browse(self, *args):
        pass

    def save(self, content):
        self.info('Write to %s' % self.output_file)
        write_file(self.output_file, content)

    # Apapun errornya pastikan logout
    def run(self, *args):
        if not self.login():
            return []
        content = None
        try:
            resp = self.browse(*args)
            if resp:
                content = resp.read()
        except:
            show_traceback()
        self.logout()
        if not content:
            return []
        if self.output_file:
            self.save(content)
        return self.parse(content)

    def parse(self, content):
        return parse(self.parser, content)

    def info(self, msg):
        print_log(msg)

    def error(self, msg):
        print_log(msg, 'ERROR')


def parse(handler, content):
    parser = handler()
    parser.feed(content)
    return parser.get_clean_data()


####################
# Numeric function #
####################
def to_float(s):
    return float(s.replace('.', '').replace(',', '.'))

#################
# Date function #
#################
def to_date(s): 
    t = s.split('-')
    y, m, d = int(t[0]), int(t[1]), int(t[2])
    return date(y, m, d)

#################
# File function #
#################
def open_file(filename):
    f = open(filename)
    content = f.read()
    f.close()
    return content

def write_file(filename, content):
    f = open(filename, 'w')
    f.write(content)
    f.close()

def get_download_filename(headers):
    info = 'content-disposition' in headers and headers['content-disposition']
    if not info:
        return
    for attrs in info.split(';'):
        t = attrs.split('=')
        if t[0].strip().lower() == 'filename' and t[1:]:
            return t[1].strip('"')

def get_download_response(response):
    headers = response.info()
    content = response.read()
    filename = get_download_filename(headers)
    return filename, content
    
############
# Show log #
############
def show_traceback():
    f = StringIO()
    traceback.print_exc(file=f)
    print(f.getvalue())
    f.close()

def print_log(s, category='INFO'):
    print('%s %s %s' % (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
          category, s))

###############
# Form parser #
###############
class FormParser(SGMLParser):
    def __init__(self):
        SGMLParser.__init__(self)
        self.form = {}
        self.inputs = {}
        self.input_list = []
        self.selects = {}
        self.select_name = ''

    def start_form(self, attrs):
        for attr in attrs:
            if attr[0] == 'action':
                self.form['action'] = attr[1]

    def start_input(self, attrs):
        if len(attrs) > 0:
            name = ''
            value = ''
            for attr in attrs:
                if attr[0] == 'name':
                    name = attr[1]
                elif attr[0] == 'value':
                    value = attr[1]
            if name:
                self.inputs[name] = value
                self.input_list.append(name)
 
    def start_select(self, attrs):
        for attr in attrs:
            if attr[0] == 'name':
                self.selects[attr[1]] = dict(option=[]) 
                self.select_name = attr[1]
            elif attr[0] == 'onchange':
                self.selects[self.select_name]['onchange'] = attr[1]
 
    def end_select(self):
        self.select_name = ''

    def start_option(self, attrs):
        if self.select_name:
            for attr in attrs:
                if attr[0] == 'value' and attr[1]:
                    self.selects[self.select_name]['option'].append(attr[1])

################
# URL function #
################
def dict2url(p):
    r = []
    for key in p:
        v = urllib.quote(p[key])
        s = '%s=%s' % (key, v)
        r.append(s)
    return '&'.join(r)


if __name__ == '__main__':
    import sys
    from optparse import OptionParser
    from pprint import pprint
    pars = OptionParser()
    pars.add_option('', '--form-file')
    option, remain = pars.parse_args(sys.argv[1:])

    if option.form_file:
        content = open_file(option.form_file)
        parser = FormParser()
        parser.feed(content)
        print('inputs')
        pprint(parser.inputs)
        print('selects')
        pprint(parser.selects)
