# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
import json
from uuid import uuid4

import pika

from pyoko import Model, field, ListNode
from pyoko.conf import settings
from pyoko.db.adapter.db_riak import BlockSave
from pyoko.exceptions import IntegrityError
from pyoko.fields import DATE_TIME_FORMAT
from pyoko.lib.utils import get_object_from_path
from zengine.client_queue import BLOCKING_MQ_PARAMS, get_mq_connection
from zengine.lib.utils import to_safe_str

UserModel = get_object_from_path(settings.USER_MODEL)




CHANNEL_TYPES = (
    # users private message hub
    (5, "Private"),
    #  a One-To-One communication between 2 user
    (10, "Direct"),
    # public chat rooms
    (15, "Public"),
)


class Channel(Model):
    """
    Represents MQ exchanges.

    is_private: Represents users exchange hub
    Each user have a durable private exchange,
     which their code_name composed from user key prefixed with "prv_"

    is_direct: Represents a user-to-user direct message exchange
    """
    mq_channel = None
    mq_connection = None

    typ = field.Integer("Type", choices=CHANNEL_TYPES)
    name = field.String("Name")
    code_name = field.String("Internal name")
    description = field.String("Description")
    owner = UserModel(reverse_name='created_channels', null=True)

    def __unicode__(self):
        return "%s (%s's %s channel)" % (self.name or '',
                                         self.owner.full_name,
                                         self.get_typ_display())

    #
    # class Managers(ListNode):
    #     user = UserModel()

    def is_private(self):
        return self.typ == 5

    @classmethod
    def get_or_create_direct_channel(cls, initiator_key, receiver_key):
        """
        Creates a  direct messaging channel between two user

        Args:
            initiator: User, who want's to make first contact
            receiver: User, other party

        Returns:
            (Channel, receiver_name)
        """
        existing = cls.objects.OR().filter(
            code_name='%s_%s' % (initiator_key, receiver_key)).filter(
            code_name='%s_%s' % (receiver_key, initiator_key))
        receiver_name = UserModel.objects.get(receiver_key).full_name
        if existing:
            channel = existing[0]
        else:
            channel_name = '%s_%s' % (initiator_key, receiver_key)
            channel = cls(is_direct=True, code_name=channel_name, typ=10).blocking_save()
        with BlockSave(Subscriber):
            Subscriber.objects.get_or_create(channel=channel,
                                             user_id=initiator_key,
                                             name=receiver_name)
            Subscriber.objects.get_or_create(channel=channel,
                                             user_id=receiver_key,
                                             name=UserModel.objects.get(initiator_key).full_name)
        return channel, receiver_name

    def get_avatar(self, user):
        if self.typ == 10:
            return self.subscriber_set.objects.exclude(user=user)[0].user.get_avatar_url()
        else:
            return None

    @classmethod
    def add_message(cls, channel_key, body, title=None, sender=None, url=None, typ=2,
                    receiver=None):
        mq_channel = cls._connect_mq()
        msg_object = Message(sender=sender, body=body, msg_title=title, url=url,
                             typ=typ, channel_id=channel_key, receiver=receiver, key=uuid4().hex)
        msg_object.setattr('unsaved', True)
        mq_channel.basic_publish(exchange=channel_key,
                                 routing_key='',
                                 body=json.dumps(msg_object.serialize()))
        return msg_object.save()

    def get_subscription_for_user(self, user_id):
        return self.subscriber_set.objects.get(user_id=user_id)

    def get_last_messages(self):
        # TODO: Try to refactor this with https://github.com/rabbitmq/rabbitmq-recent-history-exchange
        return self.message_set.objects.filter().set_params(sort="updated_at desc")[:20]

    @classmethod
    def _connect_mq(cls):
        if cls.mq_connection is None or cls.mq_connection.is_closed:
            cls.mq_connection, cls.mq_channel = get_mq_connection()
        return cls.mq_channel

    def create_exchange(self):
        """
        Creates MQ exchange for this channel
        Needs to be defined only once.
        """
        mq_channel = self._connect_mq()
        mq_channel.exchange_declare(exchange=self.code_name,
                                    exchange_type='fanout',
                                    durable=True)


    def pre_creation(self):
        if not self.code_name:
            if self.name:
                self.code_name = to_safe_str(self.name)
                self.key = self.code_name
                return
            if self.owner and self.is_private:
                self.code_name = self.owner.prv_exchange
                self.key = self.code_name
                return
            raise IntegrityError('Non-private and non-direct channels should have a "name".')
        else:
            self.key = self.code_name

    def post_save(self):
        self.create_exchange()
        # self.subscribe_owner()


class Subscriber(Model):
    """
    Permission model
    """

    mq_channel = None
    mq_connection = None

    channel = Channel()
    name = field.String("Subscription Name")
    user = UserModel(reverse_name='subscriptions')
    is_muted = field.Boolean("Mute the channel", default=False)
    pinned = field.Boolean("Pin channel to top", default=False)
    inform_me = field.Boolean("Inform when I'm mentioned", default=True)
    read_only = field.Boolean("This is a read-only subscription (to a broadcast channel)",
                              default=False)
    is_visible = field.Boolean("Show under user's channel list", default=True)
    can_manage = field.Boolean("Can manage this channel", default=False)
    can_leave = field.Boolean("Membership is not obligatory", default=True)
    last_seen_msg_time = field.TimeStamp("Last seen message's time")

    # status = field.Integer("Status", choices=SUBSCRIPTION_STATUS)

    def __unicode__(self):
        return "%s subscription of %s" % (self.name, self.user)


    @classmethod
    def _connect_mq(cls):
        if cls.mq_connection is None or cls.mq_connection.is_closed:
            cls.mq_connection, cls.mq_channel = get_mq_connection()
        return cls.mq_channel

    def get_actions(self):
        actions = [
            ('Pin', '_zops_pin_channel'),
            # ('Mute', '_zops_mute_channel'),
        ]
        if self.channel.owner == self.user or self.can_manage:
            actions.extend([
                ('Delete', '_zops_delete_channel'),
                ('Edit', '_zops_edit_channel'),
                ('Add Users', '_zops_add_members'),
                ('Add Unit', '_zops_add_unit_to_channel')
            ])
        return actions

    def is_online(self):
        # TODO: Cache this method
        if self.channel.typ == 10:
            return self.channel.subscriber_set.objects.exclude(
                user=self.user).get().user.is_online()

    def unread_count(self):
        # FIXME: track and return actual unread message count
        if self.last_seen_msg_time:
            return self.channel.message_set.objects.filter(
                timestamp__gt=self.last_seen_msg_time).count()
        else:
            return self.channel.message_set.objects.filter().count()

    def create_exchange(self):
        """
        Creates user's private exchange

        Actually user's private channel needed to be defined only once,
        and this should be happened when user first created.
        But since this has a little performance cost,
        to be safe we always call it before binding to the channel we currently subscribe
        """
        channel = self._connect_mq()
        channel.exchange_declare(exchange=self.user.prv_exchange,
                                 exchange_type='fanout',
                                 durable=True)

    @classmethod
    def mark_seen(cls, key, datetime_str):
        cls.objects.filter(key=key).update(last_seen=datetime_str)

    def bind_to_channel(self):
        """
        Binds (subscribes) users private exchange to channel exchange
        Automatically called at creation of subscription record.
        """
        if self.channel.code_name != self.user.prv_exchange:
            channel = self._connect_mq()
            channel.exchange_bind(source=self.channel.code_name, destination=self.user.prv_exchange)

    def post_creation(self):
        self.create_exchange()
        self.bind_to_channel()

    def pre_creation(self):
        if not self.name:
            self.name = self.channel.name


MSG_TYPES = (
    (1, "Info Notification"),
    (11, "Error Notification"),
    (111, "Success Notification"),
    (2, "Direct Message"),
    (3, "Broadcast Message"),
    (4, "Channel Message")
)
MESSAGE_STATUS = (
    (1, "Created"),
    (11, "Transmitted"),
    (22, "Seen"),
    (33, "Read"),
    (44, "Archived"),

)


class Message(Model):
    """
    Message model

    Notes:
        Never use directly for creating new messages! Use these methods:
            - Channel objects's **add_message()** method.
            - User object's **set_message()** method. (which also uses channel.add_message)
    """
    channel = Channel()
    sender = UserModel(reverse_name='sent_messages')
    receiver = UserModel(reverse_name='received_messages')
    typ = field.Integer("Type", choices=MSG_TYPES, default=1)
    status = field.Integer("Status", choices=MESSAGE_STATUS, default=1)
    msg_title = field.String("Title")
    body = field.String("Body")
    url = field.String("URL")

    def get_actions_for(self, user):
        actions = []
        if Favorite.objects.filter(user=user,
                                   channel=self.channel,
                                   message=self).count():
            actions.append(('Remove from favorites', '_zops_remove_from_favorites'))
        else:
            actions.append(('Add to favorites', '_zops_favorite_message'))


        if user:
            if FlaggedMessage.objects.filter(user=user, message=self).count():
                actions.append(('Remove Flag', '_zops_unflag_message'))
            else:
                actions.append(('Flag Message', '_zops_flag_message'))
            if self.sender == user:
                actions.extend([
                    ('Delete', '_zops_delete_message'),
                    ('Edit', '_zops_edit_message')
                ])
        return actions

    def serialize(self, user=None):
        """
        Serializes message for given user.

        Note:
            Should be called before first save(). Otherwise "is_update" will get wrong value.

        Args:
            user: User object

        Returns:
            Dict. JSON serialization ready dictionary object
        """
        return {
            'content': self.body,
            'type': self.typ,
            'updated_at': self.updated_at,
            'timestamp': self.updated_at,
            'is_update': hasattr(self, 'unsaved'),
            'attachments': [attachment.serialize() for attachment in self.attachment_set],
            'title': self.msg_title,
            'sender_name': self.sender.full_name,
            'sender_key': self.sender.key,
            'channel_key': self.channel.key,
            'cmd': 'message',
            'avatar_url': self.sender.avatar,
            'key': self.key,
        }

    def __unicode__(self):
        content = self.msg_title or self.body
        return "%s%s" % (content[:30], '...' if len(content) > 30 else '')

    def _republish(self):
        """
        Re-publishes updated message
        """
        mq_channel = self.channel._connect_mq()
        mq_channel.basic_publish(exchange=self.channel.key, routing_key='',
                                 body=json.dumps(self.serialize()))

    def pre_save(self):
        if not hasattr(self, 'unsaved'):
            self._republish()


ATTACHMENT_TYPES = (
    (1, "Document"),
    (11, "Spreadsheet"),
    (22, "Image"),
    (33, "PDF"),

)


class Attachment(Model):
    """
    A model to store message attachments
    """
    file = field.File("File", random_name=True, required=False)
    typ = field.Integer("Type", choices=ATTACHMENT_TYPES)
    name = field.String("File Name")
    description = field.String("Description")
    channel = Channel()
    message = Message()

    def serialize(self):
        return {
            'description': self.description,
            'file_name': self.name,
            'url': "%s%s" % (settings.S3_PUBLIC_URL, self.file)
        }

    def __unicode__(self):
        return self.name


class Favorite(Model):
    """
    A model to store users bookmarked messages
    """
    channel = Channel()
    user = UserModel()
    message = Message()
    summary = field.String("Message Summary")
    channel_name = field.String("Channel Name")

    def pre_creation(self):
        if not self.channel:
            self.channel = self.message.channel
        self.summary = self.message.body[:60]
        self.channel_name = self.channel.name


class FlaggedMessage(Model):
    """
    A model to store users bookmarked messages
    """
    channel = Channel()
    user = UserModel()
    message = Message()

    def pre_creation(self):
        self.channel = self.message.channel
