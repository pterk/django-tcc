import timeit

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from tcc import api
from tcc.models import Comment
from tcc import settings


class API(TestCase):
    usernames = ['user1', 'user2']

    def setUp(self):
        for name in self.usernames:
            u = User.objects.create(username=name, password=name)
            setattr(self, name, u)

    def tearDown(self):
        for name in self.usernames:
            User.objects.get(username=name).delete()

    def test_basic(self):
        ct = ContentType.objects.get_for_model(self.user1)
        pk = self.user1.pk
        c = api.post_comment(content_type_id=ct.id, object_pk=pk,
                             user_id=pk, comment="Root message")
        self.assertTrue(c is not None)
        comments = api.get_comments(ct.id, pk)
        self.assertEqual(len(comments), 1)
        comment = api.get_comment(c.id)
        self.assertTrue(comment is not None)
        self.assertEqual(comment.id, c.id)
        comment = api.get_comment(-1)
        self.assertTrue(comment is None)

    def test_remove(self):
        ct = ContentType.objects.get_for_model(self.user1)
        pk = self.user1.pk
        c = api.post_comment(content_type_id=ct.id, object_pk=pk,
                             user_id=pk, comment="Root message")
        self.assertTrue(c is not None)
        c = api.remove_comment(c.id, self.user1)
        self.assertTrue(c is not None)
        self.assertTrue(c.is_removed)
        removed = api.get_comments_removed(
            content_type_id=ct.id, object_pk=pk)
        self.assertEqual(len(removed), 1)
        # restore_comment with wrong user
        x = api.restore_comment(c.id, self.user2)
        self.assertTrue(x is None)
        c = api.restore_comment(c.id, self.user1)
        self.assertTrue(c is not None)
        self.assertFalse(c.is_removed)
        # non-exising comments should return None
        x = api.restore_comment(-1, self.user1)
        self.assertEqual(x, None)
        x = api.remove_comment(-1, self.user1)
        self.assertEqual(x, None)
        # remove_comment with wrong user
        orgid = c.id
        c = api.remove_comment(orgid, self.user2)
        self.assertTrue(c is None)
        c = api.get_comment(orgid)
        self.assertFalse(c.is_removed)
        removed = api.get_comments_removed(
            content_type_id=ct.id, object_pk=pk)
        self.assertEqual(len(removed), 0)

    def test_approve(self):
        ct = ContentType.objects.get_for_model(self.user1)
        pk = self.user1.pk
        c = api.post_comment(content_type_id=ct.id, object_pk=pk,
                             user_id=pk, comment="Root message")
        self.assertTrue(c is not None)
        # wrong user
        x = api.approve_comment(c.id, self.user2)
        self.assertTrue(x is None)
        c = api.approve_comment(c.id, self.user1)
        self.assertTrue(c is not None)
        self.assertTrue(c.is_approved)
        # wrong user
        x = api.disapprove_comment(c.id, self.user2)
        self.assertTrue(x is None)
        c = api.disapprove_comment(c.id, self.user1)
        self.assertTrue(c is not None)
        self.assertFalse(c.is_approved)
        disapproved = api.get_comments_disapproved(
            content_type_id=ct.id, object_pk=pk)
        self.assertEqual(len(disapproved), 1)
        c = api.approve_comment(c.id, self.user1)
        self.assertTrue(c is not None)
        self.assertTrue(c.is_approved)
        disapproved = api.get_comments_disapproved(
            content_type_id=ct.id, object_pk=pk)
        self.assertEqual(len(disapproved), 0)
        c = api.approve_comment(-1, self.user1)
        self.assertEqual(c, None)
        c = api.disapprove_comment(-1, self.user1)
        self.assertEqual(c, None)

    def test_post_comment(self):
        ct = ContentType.objects.get_for_model(self.user1)
        pk = self.user1.pk
        p = api.post_comment(content_type_id=ct.id, object_pk=pk,
                             user_id=pk, comment="Root message")
        self.assertEqual(p.path,  u'1'.zfill(settings.STEPLEN))
        c = api.post_comment(content_type_id=ct.id, object_pk=pk,
                             user_id=pk, comment="Reply", parent_id=p.id)
        self.assertEqual(c.path,  u'1'.zfill(settings.STEPLEN)+u'2'.zfill(settings.STEPLEN))
        self.assertEqual(c.get_parents()[0].id, p.id)
        self.assertEqual(len(p.get_parents()), 0)
        self.assertEqual(p.get_replies()[0].id, c.id)
        self.assertEqual(len(c.get_replies()), 0)
        self.assertEqual(api.get_comment_replies(p.id)[0].id, c.id)
        self.assertEqual(api.get_comment_parents(c.id)[0].id, p.id)
        tp = api.get_comment_thread(p.id)
        tc = api.get_comment_thread(c.id)
        self.assertEqual(len(tp), 2)
        self.assertEqual(len(tc), 2)
        # Non existing parent
        c = api.post_comment(content_type_id=ct.id, object_pk=pk,
                             user_id=pk, comment="Reply", parent_id=-1)
        self.assertEqual(c, None)

    def test_post_reply(self):
        ct = ContentType.objects.get_for_model(self.user1)
        pk = self.user1.pk
        p = api.post_comment(content_type_id=ct.id, object_pk=pk,
                             user_id=pk, comment="Root message")
        self.assertEqual(p.path,  u'1'.zfill(settings.STEPLEN))
        c = api.post_reply(user_id=pk, comment="Reply", parent_id=p.id)
        self.assertEqual(c.path,  u'1'.zfill(settings.STEPLEN)+u'2'.zfill(settings.STEPLEN))
        self.assertEqual(c.get_parents()[0].id, p.id)
        self.assertEqual(p.get_replies()[0].id, c.id)
        tp = api.get_comment_thread(p.id)
        tc = api.get_comment_thread(c.id)
        self.assertEqual(len(tp), 2)
        self.assertEqual(len(tc), 2)
        # Non existing parent
        c = api.post_reply(user_id=pk, comment="Reply", parent_id=-1)
        self.assertEqual(c, None)

    def test_open(self):
        ct = ContentType.objects.get_for_model(self.user1)
        pk = self.user1.pk
        p = api.post_comment(content_type_id=ct.id, object_pk=pk,
                             user_id=pk, comment="Root message")
        self.assertTrue(p is not None)
        # wrong user
        x = api.open_comment(p.id, self.user2)
        self.assertTrue(x is None)
        p = api.open_comment(p.id, self.user1)
        self.assertTrue(p is not None)
        self.assertTrue(p.is_open)
        c = api.post_reply(user_id=pk, comment="Reply", parent_id=p.id)
        self.assertTrue(c is not None)
        x = api.close_comment(p.id, self.user2)
        self.assertTrue(x is None)
        p = api.close_comment(p.id, self.user1)
        self.assertTrue(p is not None)
        self.assertFalse(p.is_open)
        c = api.post_reply(user_id=pk, comment="Reply", parent_id=p.id)
        self.assertEqual(c, None)
        c = api.open_comment(-1, self.user1)
        self.assertEqual(c, None)
        c = api.close_comment(-1, self.user1)
        self.assertEqual(c, None)

    def test_user_comments(self):
        ct = ContentType.objects.get_for_model(self.user1)
        pk = self.user1.pk
        p = api.post_comment(content_type_id=ct.id, object_pk=pk,
                             user_id=pk, comment="Root message")
        self.assertTrue(p is not None)
        uc = api.get_user_comments(pk)
        self.assertEqual(len(uc), 1)
        c = api.post_reply(user_id=pk, comment="Reply", parent_id=p.id)
        self.assertTrue(c is not None)
        uc = api.get_user_comments(pk)
        self.assertEqual(len(uc), 2)
        c = api.post_reply(user_id=self.user2.pk, comment="Reply", parent_id=p.id)
        self.assertTrue(c is not None)
        uc = api.get_user_comments(pk)
        self.assertEqual(len(uc), 2)
        uc = api.get_user_comments(self.user2.pk)
        self.assertEqual(len(uc), 1)
        uc = api.get_user_comments(self.user2.pk, content_type_id=ct.id)
        self.assertEqual(len(uc), 1)
        uc = api.get_user_comments(
            self.user2.pk, content_type_id=ct.id, object_pk=pk)
        self.assertEqual(len(uc), 1)
        uc = api.get_user_comments(
            self.user2.pk, content_type_id=ct.id, object_pk=pk, site_id=1)

    def test_tree_depth(self):
        ct = ContentType.objects.get_for_model(self.user1)
        pk = self.user1.pk
        for _ in range(3):
            p = api.post_comment(content_type_id=ct.id, object_pk=pk,
                                 user_id=pk, comment="Root message")
            c = api.post_reply(user_id=pk, comment="Reply", parent_id=p.id)
            self.assertTrue(c is not None)
            if settings.MAX_DEPTH > 2:
                r1 = api.post_reply(user_id=pk, comment="Reply", parent_id=c.id)
                self.assertTrue(c is not None)
                r2 = api.post_reply(user_id=pk, comment="Reply", parent_id=c.id)
                self.assertTrue(c is not None)
            if settings.MAX_DEPTH > 3:
                r1a = api.post_reply(user_id=pk, comment="Reply", parent_id=r1.id)
                self.assertTrue(c is not None)
        tree = api.get_comments_as_tree(ct.id, pk)
        self.assertEqual(len(tree), 3)
        if settings.MAX_DEPTH == 2:
            self.assertEqual(len(tree[0].replies), 1)
        if settings.MAX_DEPTH > 2:
            self.assertEqual(len(tree[0].replies[0].replies), 2)
        if settings.MAX_DEPTH > 3:
            self.assertEqual(len(tree[0].replies[0].replies[0].replies), 1)
        tree = api.get_comments_limited_as_tree(ct.id, pk)
        self.assertEqual(len(tree), 3)
        if settings.MAX_DEPTH == 2:
            self.assertEqual(len(tree[0].replies), 1)
        if settings.MAX_DEPTH > 2:
            self.assertEqual(len(tree[0].replies[0].replies), 2)
        if settings.MAX_DEPTH > 3:
            self.assertEqual(len(tree[0].replies[0].replies[0].replies), 1)


class ORM(TestCase):
    usernames = ['user1', 'user2']

    def setUp(self):
        for name in self.usernames:
            u = User.objects.create(username=name, password=name)
            setattr(self, name, u)

    def tearDown(self):
        for name in self.usernames:
            User.objects.get(username=name).delete()

    def test_replies(self):
        ct = ContentType.objects.get_for_model(self.user1)
        pk = self.user1.pk
        for _ in range(5):
            p = api.post_comment(content_type_id=ct.id, object_pk=pk,
                                 user_id=pk, comment="Root message")
            for __ in range(settings.REPLY_LIMIT+3):
                c = api.post_reply(user_id=pk, comment="Reply", parent_id=p.id)
        self.assertEqual(api.get_comments_limited(ct.id, pk).count(), 5*(settings.REPLY_LIMIT+1))
