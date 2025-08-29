from django.core.management.base import BaseCommand
from django.core.mail import EmailMessage
from django.conf import settings
from aws_saas.models import SesEmailIdentity
import boto3
import traceback


class Command(BaseCommand):
    help = u'SES - Sync Email Identities'
    job_name = 'ses_sync_identities'

    def handle(self, *args, **options):
        try:
            self.client = boto3.client('sesv2', region_name=settings.SES_AWS_REGION)
            self.run()
        except:
            tb = traceback.format_exc()
            self.send_error_notification(tb)

    def run(self):
        email_identities = self.client.list_email_identities()

        for obj in email_identities['EmailIdentities']:
            email_identity = SesEmailIdentity.objects.filter(identity=obj['IdentityName']).first()
            if not email_identity:
                SesEmailIdentity.objects.create(type=obj['IdentityType'].lower(), identity=obj['IdentityName'], sending_enabled=obj['SendingEnabled'])
                self.stdout.write(obj['IdentityName'])

        self.stdout.write(f"SES Sync - Total: {len(email_identities['EmailIdentities'])}")

    def send_error_notification(self, tb, concat=None):
        html = str(tb)
        if concat:
            html += concat

        email = EmailMessage(subject='ERROR: SES - Sync Email Identities', body=html, from_email=settings.EMAIL_ADMIN, to=[settings.EMAIL_ADMIN])
        email.content_subtype = "html"
        email.send(fail_silently=True)
        self.stdout.write(html)
