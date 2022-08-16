import boto3
from django.conf import settings


class AwsSesEmailIdentity():

    def __init__(self, email_identity):
        self.email_identity = email_identity
        self.client = boto3.client('sesv2', aws_access_key_id=settings.SES_AWS_ACCESS_KEY_ID, aws_secret_access_key=settings.SES_AWS_SECRET_ACCESS_KEY, region_name=settings.SES_AWS_REGION)

    def create(self):
        return self.client.create_email_identity(EmailIdentity=self.email_identity.identity)

    def delete(self):
        return self.client.delete_email_identity(EmailIdentity=self.email_identity.identity)

    def get_email_identity(self):
        return self.client.get_email_identity(EmailIdentity=self.email_identity.identity)

    def list_email_identities(self):
        return self.client.list_email_identities()

    def update_email_data(self):
        data = self.get_email_identity()

        if 'VerifiedForSendingStatus' in data:
            self.email_identity.sending_enabled = data.get('VerifiedForSendingStatus')
            self.email_identity.save()

        return self.email_identity
