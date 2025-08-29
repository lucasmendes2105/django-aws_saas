from django.core.management.base import BaseCommand
from django.core.mail import EmailMessage
from django.conf import settings
from aws_saas.models import Certificate, CertificateDomain
import boto3
import traceback


class Command(BaseCommand):
    help = u'ACM - Sync Certificates'
    job_name = 'acm_sync_certificates'

    def handle(self, *args, **options):
        try:
            self.client = boto3.client('acm', region_name=settings.ACM_AWS_REGION) # Usa a role da instância EC2 (Elastic Beanstalk)
            self.run()
        except:
            tb = traceback.format_exc()
            self.send_error_notification(tb)

    def run(self):
        list_certificates = self.aws_list_certificates()

        for obj in list_certificates['CertificateSummaryList']:
            certificate_id = obj['CertificateArn'].split('certificate/')[1]
            certificate = Certificate.objects.filter(certificate_id=certificate_id).first()

            describe = self.aws_describe_certificate(arn=obj['CertificateArn'])

            if not certificate:
                data = {
                    'certificate_id': certificate_id,
                    'domain': describe['Certificate']['DomainName'],
                    'status': describe['Certificate']['Status'],
                    'in_use': False if len(describe['Certificate']['InUseBy']) == 0 else True,
                    'is_qualified': False if describe['Certificate']['RenewalEligibility'] == 'INELIGIBLE' else True,
                    'validation_method': describe['Certificate']['DomainValidationOptions'][0]['ValidationMethod'].lower(),
                    'arn': describe['Certificate']['CertificateArn'],
                    'created_at': describe['Certificate']['CreatedAt'].replace(tzinfo=None) if 'CreatedAt' in describe['Certificate'] else None,
                    'issued_at': describe['Certificate']['IssuedAt'].replace(tzinfo=None) if 'IssuedAt' in describe['Certificate'] else None,
                }

                certificate_db = Certificate.objects.create(**data)

                for domain in describe['Certificate']['DomainValidationOptions']:
                    domain_data = {
                        'certificate': certificate_db,
                        'domain': domain['DomainName'],
                        'status': domain['ValidationStatus'],
                    }
                    if domain['ValidationMethod'] == 'DNS' and 'ResourceRecord' in domain:
                        domain_data.update({
                            'type': domain['ResourceRecord']['Type'],
                            'cname_name': domain['ResourceRecord']['Name'],
                            'cname_value': domain['ResourceRecord']['Value'],
                        })

                    elif domain['ValidationMethod'] == 'EMAIL' and 'ValidationEmails' in domain:
                        emails = ', '.join(domain['ValidationEmails'])
                        emails = emails.replace(domain['DomainName'], '')
                        domain_data.update({
                            'emails': emails
                        })

                    CertificateDomain.objects.create(**domain_data)

                self.stdout.write(data['domain'])
            else:
                certificate.status = describe['Certificate']['Status']
                certificate.is_use = False if len(describe['Certificate']['InUseBy']) == 0 else True
                certificate.is_qualified = False if describe['Certificate']['RenewalEligibility'] == 'INELIGIBLE' else True
                certificate.save()
                self.stdout.write(certificate.domain)

        self.stdout.write(f"Total: {len(list_certificates['CertificateSummaryList'])}")

    def aws_list_certificates(self):
        return self.client.list_certificates()

    def aws_describe_certificate(self, arn):
        return self.client.describe_certificate(CertificateArn=arn)

    def send_error_notification(self, tb, concat=None):
        html = str(tb)
        if concat:
            html += concat

        email = EmailMessage(subject='ERROR: ACM - Sync Certificates', body=html, from_email=settings.EMAIL_ADMIN, to=[settings.EMAIL_ADMIN])
        email.content_subtype = "html"
        email.send(fail_silently=True)
        self.stdout.write(html)
