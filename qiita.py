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
    global BASE_URL
    global qiita_user
    global qiita_token

    BASE_URL = 'https://qiita.com/api/v1'

    settings = sublime.load_settings('Qiita.sublime-settings')
    qiita_user = settings.get('username')
    qiita_token = settings.get('token')


class QiitaPostNewItemCommand(QiitaCommandBase):

    def run(self):
        thread = NewItemThread(self.window)
        thread.start()
        ThreadProgress(thread, 'Post new item to qiita', 'Done.')

    # def is_enabled(self):
    #     item = self.window.active_view().settings().get('Qiita_item')
    #     return True


class QiitaOpenItemCommand(QiitaCommandBase):

    def run(self):
        thread = ListItemsThread(self.window)
        thread.start()
        ThreadProgress(thread, 'Loding items from qiita', 'Done.')


class QiitaOpenItemUrlCommand(QiitaCommandBase):

    def run(self):
        webbrowser.open_new_tab(self.qiita_item().get('url'))

    def is_enabled(self):
        return self.qiita_item() != None and self.qiita_item().get('url') != None


class NewItemThread(threading.Thread):

    def __init__(self, window):
        self.window = window
        threading.Thread.__init__(self)

    def run(self):
        data = self.get_item_data()
        url = BASE_URL + '/items?token=%s' % qiita_token
        headers = {"Accept": "application/json", "Content-type": "application/json"}

        req = request.Request(url, data, headers)
        res = api_request(req)

        webbrowser.open_new_tab(res.get('url'))

    def get_item_data(self):
        item_data = {}

        # TODO: sample data
        item_data['title'] = 'sublime post'
        item_data['tags'] = [{'name': 'test'}]
        item_data['private'] = True

        view = self.window.active_view()
        text = view.substr(sublime.Region(0, view.size()))
        item_data['body'] = text

        return bytes(json.dumps(item_data), 'UTF-8')


class ListItemsThread(threading.Thread):

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
            tag_str = ''
            for tag in item.get('tags'):
                if tag_str != '':
                    tag_str += ', '
                tag_str += tag.get('name')

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

        # info_view = self.window.create_output_panel('qiita_info')
        # info_view.run_command('append', {'characters': 'タイトル: %s\n' % item.get('title')})
        # info_view.run_command('append', {'characters': '更新時間: %s\n' % item.get('updated_at')})
        # info_view.run_command('append', {'characters': '作成時間: %s\n' % item.get('created_at')})

        # self.window.run_command('show_panel', {'panel': 'output.qiita_info'})
    def build_view(self, view, item):
        view.settings().set('Qiita_item', item)

        view.run_command('append', {'characters': item.get('raw_body')})


class QiitaCommandBase(sublime_plugin.WindowCommand):

    def __init__(self, window):

        self.window = window

    def qiita_item(self):
        return self.window.active_view().settings().get('Qiita_item')

def api_request(url):
    res = request.urlopen(url)
    encoding = res.headers.get_content_charset()
    return json.loads(res.read().decode(encoding))
