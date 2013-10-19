import sublime
import sublime_plugin

import json
import os
import sys
import threading
import urllib.request
import webbrowser

from .thread_progress import ThreadProgress


def plugin_loaded():
    global TITLE_LINE
    global TAGS_LINE
    global BASE_URL
    global HEADERS
    global qiita_user
    global qiita_token

    TITLE_LINE = 0
    TAGS_LINE = 1
    BASE_URL = 'https://qiita.com/api/v1'
    HEADERS = {"Accept": "application/json", "Content-type": "application/json"}

    settings = sublime.load_settings('Qiita.sublime-settings')
    qiita_user = settings.get('username')
    qiita_token = settings.get('token')


def api_request(url_or_request):
    res = urllib.request.urlopen(url_or_request)
    encoding = res.headers.get_content_charset()
    return json.loads(res.read().decode(encoding))


def build_tag_str(tags):
    tag_str = ''
    for tag in tags:
        if len(tag_str) > 0:
            tag_str += ', '

        tag_str += tag.get('name')

    return tag_str


class QiitaCommandBase(sublime_plugin.WindowCommand):

    def __init__(self, window):
        self.window = window

    def qiita_item(self):
        return self.window.active_view().settings().get('qiita_item')


class QiitaPostNewItemCommand(QiitaCommandBase):

    def run(self, private="true"):
        thread = PostNewItemThread(self.window, private=="true")
        thread.start()
        ThreadProgress(thread, 'Post new item to qiita', 'Done.')

    def is_enabled(self):
        return self.qiita_item() == None or self.qiita_item().get('url') == None


class QiitaGetItemsCommand(QiitaCommandBase):

    def run(self):
        thread = GetItemsThread(self.window)
        thread.start()
        ThreadProgress(thread, 'Geting item list from qiita', 'Done.')


class QiitaUpdateItemCommand(QiitaCommandBase):

    def run(self):
        uuid = self.qiita_item().get('uuid')
        thread = UpdateItemThread(self.window, uuid)
        thread.start()
        ThreadProgress(thread, 'Update item to qiita', 'Done.')

    def is_enabled(self):
        return self.qiita_item() != None and self.qiita_item().get('url') != None


class QiitaOpenItemUrlCommand(QiitaCommandBase):

    def run(self):
        webbrowser.open_new_tab(self.qiita_item().get('url'))

    def is_enabled(self):
        return self.qiita_item() != None and self.qiita_item().get('url') != None


class BuildItem():

    def __init__(self, window, private):
        self.window = window
        self.private = private

    def get_item_data(self):
        view = self.window.active_view()
        all_lines = view.lines(sublime.Region(0, view.size()))

        item_data = {}

        item_data['title'] = view.substr(all_lines[TITLE_LINE])
        item_data['tags'] = self.build_tags(view.substr(all_lines[TAGS_LINE]))
        item_data['private'] = self.private

        start = all_lines[TAGS_LINE + 1].begin()
        body_region = sublime.Region(start, view.size())
        item_data['body'] = view.substr(body_region)

        return bytes(json.dumps(item_data), 'UTF-8')

    def build_tags(self, line):
        tags = []

        for tag_str in line.replace(' ', '').split(','):
            tag = { 'name': tag_str }
            tags.append(tag)

        return tags


class PostNewItemThread(threading.Thread, BuildItem):

    def __init__(self, window, private):
        BuildItem.__init__(self, window, private)
        threading.Thread.__init__(self)

    def run(self):
        data = self.get_item_data()
        url = BASE_URL + '/items?token=%s' % qiita_token

        req = urllib.request.Request(url, data, HEADERS)
        res = api_request(req)


class UpdateItemThread(threading.Thread, BuildItem):

    def __init__(self, window, uuid):
        self.window = window
        self.uuid = uuid
        threading.Thread.__init__(self)

    def run(self):
        data = self.get_item_data()
        url = BASE_URL + '/items/%s?token=%s' % ( self.uuid, qiita_token)

        req = urllib.request.Request(url, data=data, headers=HEADERS, method='PUT')
        res = api_request(req)

        webbrowser.open_new_tab(res.get('url'))


class GetItemsThread(threading.Thread):

    def __init__(self, window):
        self.window = window
        threading.Thread.__init__(self)

    def run(self):
        url = BASE_URL + '/users/%s/items?token=%s' % (qiita_user, qiita_token)
        self.full_items = api_request(url)

        items = []
        for item in self.full_items:
            title = item.get('title')
            updated_at_in_words = item.get('updated_at_in_words')
            tag_str = build_tag_str(item.get('tags'))

            item_info = [title, "更新：" + updated_at_in_words + " タグ：" + tag_str]
            items.append(item_info)

        self.window.show_quick_panel(items, self.on_done)

    def on_done(self, index):
        if index == -1:
            return

        uuid = self.full_items[index].get('uuid')
        thread = GetItemThread(self.window, uuid)
        thread.start()
        ThreadProgress(thread, 'Geting item from qiita', 'Done.')


class GetItemThread(threading.Thread):

    def __init__(self, window, uuid):
        self.window = window
        self.uuid = uuid
        threading.Thread.__init__(self)

    def run(self):
        url = BASE_URL + '/items/%s?token=%s' % (self.uuid, qiita_token)

        item = api_request(url)

        view = sublime.active_window().new_file()
        self.build_view(view, item)

    def build_view(self, view, item):
        view.settings().set('qiita_item', item)

        view.run_command('append', {'characters': item.get('title') + "\n"})
        view.run_command('append', {'characters': build_tag_str(item.get('tags')) + "\n"})
        view.run_command('append', {'characters': item.get('raw_body')})

