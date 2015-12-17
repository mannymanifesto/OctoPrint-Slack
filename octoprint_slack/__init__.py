# coding=utf-8
from __future__ import absolute_import

import octoprint.plugin
import os
import json
import requests

class SlackPlugin(octoprint.plugin.SettingsPlugin,
                  octoprint.plugin.TemplatePlugin,
                  octoprint.plugin.EventHandlerPlugin):

    ## SettingsPlugin

    def get_settings_defaults(self):
        return dict(
                webhook_url="",
                print_events=dict(
                    PrintStarted=dict(
                        Enabled=True,
                        Message="A new print has started! :muscle:",
                        Fallback="Print started! Filename: {filename}",
                        Color="good",
                        ),
                    PrintFailed=dict(
                        Enabled=True,
                        Message="Oh no! The print has failed... :rage2:",
                        Fallback="Print failed! Filename: {filename}",
                        Color="danger",
                        ),
                    PrintCancelled=dict(
                        Enabled=True,
                        Message="Uh oh... someone cancelled the print! :crying_cat_face:",
                        Fallback="Print cancelled! Filename: {filename}",
                        Color="danger",
                        ),
                    PrintDone=dict(
                        Enabled=True,
                        Message="Print finished successfully! :thumbsup:",
                        Fallback="Print started! Filename: {filename}, Time: {time}",
                        Color="good",
                        ),
                    PrintPaused=dict(
                        Enabled=True,
                        Message="Printing has been paused... :sleeping:",
                        Fallback="Print paused... Filename: {filename}",
                        Color="warning",
                        ),
                    PrintResumed=dict(
                        Enabled=True,
                        Message="Phew! Printing has been resumed! Back to work... :hammer:",
                        Fallback="Print resumed! Filename: {filename}",
                        Color="good",
                        ),
                    ),
                )

    def get_settings_version(self):
        return 2

    def on_settings_migrate(self, target, current):
        defaults = self.get_settings_defaults()
        if current is None or current == 1:
            events = self._settings.get(['events'])
            # migrate events
            print_events = self._settings.get(['print_events'])
            if events:
                for event in events:
                    if not events[event]:
                        self._settings.set_boolean(['print_events',event,'Enabled'], False)
            # remove old settings if there
            self._settings.set(['enabled'], None)
            self._settings.set(['events'], None)
            # clean up old fallback messages from <1.2.7 oversaving
            for event in print_events:
                self._settings.set(['print_events',event,'Fallback'], None)

    ## TemplatePlugin

    def get_template_configs(self):
        return [dict(type="settings", name="Slack", custom_bindings=False)]

    ## EventPlugin

    def on_event(self, event, payload):
        events = self._settings.get(['print_events'])

        if event in events and events[event] and events[event]['Enabled']:

            webhook_url = self._settings.get(['webhook_url'])
            if not webhook_url:
                self._logger.exception("Slack Webhook URL not set!")
                return

            filename = os.path.basename(payload["file"])
            if payload['origin'] == 'local':
                origin = "Local"
            elif payload['origin'] == 'sdcard':
                origin = "SD Card"
            else:
                origin = payload['origin']

            message = {}

            ## bot display settings

            ## if no username is set, it will default to the webhook username
            username = self._settings.get(['bot_username'])
            if username:
                message['username'] = username

            ## if an icon is set, use that. if not, use the emoji.
            ## if neither are set, it will default to the webhook icon/emoji
            icon_url = self._settings.get(['bot_icon_url'])
            icon_emoji = self._settings.get(['bot_icon_emoji'])
            if icon_url:
                message['icon_url'] = icon_url
            elif icon_emoji:
                message['icon_emoji'] = icon_emoji

            ## message settings
            message['attachments'] = [{}]
            attachment = message['attachments'][0]
            attachment['fields'] = []
            attachment['fields'].append( { "title": "Filename", "value": filename, "short": True } )
            attachment['fields'].append( { "title": "Origin", "value": origin, "short": True } )

            ## event settings
            event_item = events.get(event)
            event_default = self.get_settings_defaults().get('print_events').get(event)
            ## if no value is set, use the default settings
            event_merged = event_default
            event_merged.update({k:v for k,v in event_item.iteritems() if v})

            import datetime
            import octoprint.util
            if "time" in payload and payload["time"]:
                elapsed_time = octoprint.util.get_formatted_timedelta(datetime.timedelta(seconds=payload["time"]))
            else:
                elapsed_time = ""

            attachment['fallback'] = event_merged['Fallback'].format({'filename': filename, 'time':elapsed_time})
            attachment['pretext'] = event_merged['Message']
            attachment['color'] = event_merged['Color']

            self._logger.debug("Attempting post of Slack message: {}".format(message))
            try:
                res = requests.post(webhook_url, data=json.dumps(message))
            except Exception, e:
                self._logger.exception("An error occurred connecting to Slack:\n {}".format(e.message))
                return

            if not res.ok:
                self._logger.exception("An error occurred posting to Slack:\n {}".format(res.text))
                return

            self._logger.debug("Posted event successfully to Slack!")

        else:
            self._logger.debug("Slack not configured for event.")
            return

__plugin_name__ = "Slack"
__plugin_implementation__ = SlackPlugin()
