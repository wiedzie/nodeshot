from django.db import models
from django.utils.translation import ugettext_lazy as _, ugettext as __
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.urlresolvers import reverse
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic
from django.contrib.sites.models import Site
from django.conf import settings

from nodeshot.core.base.models import BaseDate

NOTIFICATION_TYPE_CHOICES = [(key, _(key)) for key,value in settings.NODESHOT['NOTIFICATIONS']['TEXTS'].iteritems()]


class Notification(BaseDate):
    """
    Notification Model
    """
    type = models.CharField(_('type'), max_length=64, choices=NOTIFICATION_TYPE_CHOICES)
    from_user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=_('from user'), related_name='notifications_sent', blank=True, null=True)
    to_user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=_('to user'), related_name='notifications_received')
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField(blank=True, null=True)
    related_object = generic.GenericForeignKey('content_type', 'object_id')
    text = models.CharField(_('text'), max_length=120, blank=True)    
    is_read = models. BooleanField(_('read?'), default=False)
    
    class Meta:
        app_label = 'notifications'
        ordering = ('-id',)
    
    def __unicode__(self):
        return 'notification #%s' % self.id
    
    def clean(self, *args, **kwargs):
        """ Custom validation """
        if self.from_user and self.from_user_id == self.to_user_id:
            raise ValidationError(_('A user cannot send a notification to herself/himself'))
    
    def save(self, *args, **kwargs):
        """
        custom save method to send email and push notification
        """
        created = self.pk is None
        super(Notification, self).save(*args, **kwargs)
        if created:
            # notifications are sent after they have been successfully created
            self.send_notifications()
    
    def send_notifications(self):
        """ send notifications to recipient user according to her settings """
        self.send_email()
        #self.send_mobile()
    
    def send_email(self):
        """ send email notification according to user settings """
        # send only if user notification setting is set to true
        if getattr(self.to_user.email_notification_settings, self.type, False):
            send_mail(_(self.type), self.email_message, settings.DEFAULT_FROM_EMAIL, [self.to_user.email])
            return True
        else:
            # return false otherwise
            return False
    
    def send_mobile(self):
        """ send push notification according to user settings """
        raise NotImplementedError('mobile notifications not implemented yet')
    
    @property
    def email_message(self):
        # compose complete email text
        site = Site.objects.get(pk=settings.SITE_ID)
        action_url = self.get_action()
        if action_url != '' and not action_url.startswith('http'):
            action_url = "%s://%s%s" % (getattr(settings, 'PROTOCOL', 'http'), site.domain, action_url)
        hello_text = __("""Hi %s,""" % self.to_user.get_full_name())
        action_text = __("""\n\nMore details here: %s""") % action_url if action_url != "" else ""
        explain_text = __("""This is an automatic notification sent from from %s.\nIf you want to stop receiving this notification edit your email notification settings here: %s""") % (site.name, 'TODO')
        
        return "%s\n\n%s%s\n\n%s" % (hello_text, self.text, action_text, explain_text)
    
    def get_action(self):
        if self.type == 'custom':
            return ''
        
        action = settings.NODESHOT['NOTIFICATIONS']['ACTIONS'].get(self.type, None)
        
        if not action:
            return ''
        
        if action.startswith('reverse'):
            return eval(action)