from django.core.mail import EmailMessage
from django.http import Http404
from django.conf import settings
from ..models import SesEmailEvent
import json


class AwsSesEmailEvent:

    def __init__(self, request, token):
        self.request = request
        self.token = token
        self.body = json.loads(request.body) if self.request.method == 'POST' else None

    def run(self):
        if self.request.method != 'POST':
            raise Http404

        if self.token != settings.SES_AWS_SNS_TOKEN:
            return

        if self.body['Type'] == 'SubscriptionConfirmation':
            self.subscription_confirmation()
            return

        if self.body['Type'] != 'Notification':
            return

        message = json.loads(self.body['Message'])

        if message['eventType'] == 'Bounce':
            self.bounce(message)

        elif message['eventType'] == 'Complaint':
            self.complaint(message)

        elif message['eventType'] == 'Delivery':
            self.delivery(message)

        elif message['eventType'] == 'Reject':
            self.reject(message)

        elif message['eventType'] == 'DeliveryDelay':
            self.delivery_delay(message)

    def bounce(self, message):
        recipients = message['bounce']['bouncedRecipients']
        for recipient in recipients:
            data = {
                'email': recipient['emailAddress'],
                'event_type': message['eventType'],
                'bounce_type': message['bounce']['bounceType'],
                'bounce_sub_type': message['bounce']['bounceSubType'],
                'recipient_status': recipient['status']
            }
            SesEmailEvent.objects.create(**data)

    def complaint(self, message):
        recipients = message['complaint']['complainedRecipients']
        for recipient in recipients:
            data = {
                'email': recipient['emailAddress'],
                'event_type': message['eventType'],
                'complaint_feedback_type': message['complaint']['complaintFeedbackType'],
            }
            SesEmailEvent.objects.create(**data)

    def delivery(self, message):
        recipients = message['delivery']['recipients']
        for recipient in recipients:
            data = {
                'email': recipient,
                'event_type': message['eventType'],
            }
            SesEmailEvent.objects.create(**data)

    def reject(self, message):
        recipients = message['mail']['destination']
        for recipient in recipients:
            data = {
                'email': recipient,
                'event_type': message['eventType'],
                'reject_reason': message['reject']['reason']
            }
            SesEmailEvent.objects.create(**data)

    def delivery_delay(self, message):
        recipients = message['deliveryDelay']['delayedRecipients']
        for recipient in recipients:
            data = {
                'email': recipient['emailAddress'],
                'event_type': message['eventType'],
                'recipient_status': recipient['status']
            }
            SesEmailEvent.objects.create(**data)

    def subscription_confirmation(self):
        html = self.body['SubscribeURL']
        email = EmailMessage(subject='SubscriptionConfirmation', body=html, from_email=settings.EMAIL_ADMIN, to=[settings.EMAIL_ADMIN, ])
        email.content_subtype = "html"
        email_send = email.send(fail_silently=True)
        return email_send
