
import pdb
import boto3
from django.conf import settings

from ..models import LoadBalancerListener


class ACMRequestCertificate():

    def __init__(self, certificate):
        self.certificate = certificate
        self.client = boto3.client('acm', aws_access_key_id=settings.ACM_AWS_ACCESS_KEY_ID, aws_secret_access_key=settings.ACM_AWS_SECRET_ACCESS_KEY, region_name=settings.ACM_AWS_REGION)

    def request(self):
        alternative_names = self.certificate.certificatedomain_set.values_list('domain', flat=True).all()

        response = self.aws_request_certificate(domain=self.certificate.domain, alternative_names=list(alternative_names), validation_method=self.certificate.validation_method.upper(), idempotency_token=str(self.certificate.id))
        if 'CertificateArn' in response:
            certificate_id = response['CertificateArn'].split('certificate/')[1]
            self.certificate.certificate_id = certificate_id
            self.certificate.arn = response['CertificateArn']
            self.certificate.status = 'requested'
            self.certificate.save()
            return self.certificate
        else:
            return None

    def update_data(self):
        describe = self.aws_describe_certificate(self.certificate.arn)
        if 'Certificate' not in describe:
            return False

        self.certificate.status = describe['Certificate']['Status']
        self.certificate.issued_at = describe['Certificate']['IssuedAt'].replace(tzinfo=None) if 'IssuedAt' in describe['Certificate'] else None
        self.certificate.is_qualified = False if describe['Certificate']['RenewalEligibility'] == 'INELIGIBLE' else True
        self.certificate.in_use = False if len(describe['Certificate']['InUseBy']) == 0 else True
        self.certificate.save()

        for domain_validation in describe['Certificate']['DomainValidationOptions']:
            if domain_validation['ValidationMethod'] == 'DNS' and 'ResourceRecord' in domain_validation:
                self.certificate.certificatedomain_set.filter(domain=domain_validation['DomainName']).update(cname_name=domain_validation['ResourceRecord']['Name'], cname_value=domain_validation['ResourceRecord']['Value'], status=domain_validation['ValidationStatus'], type='CNAME')
            elif domain_validation['ValidationMethod'] == 'EMAIL' and 'ValidationEmails' in domain_validation:
                emails = ', '.join(domain_validation['ValidationEmails'])
                emails = emails.replace(domain_validation['DomainName'], '')
                self.certificate.certificatedomain_set.filter(domain=domain_validation['DomainName']).update(emails=emails, status=domain_validation['ValidationStatus'], type='EMAIL')

        return self.certificate

    def certificate_listeners(self, operation):
        listeners = LoadBalancerListener.objects.all()
        for listener in listeners:
            if operation == 'add':
                listener.certificates.add(self.certificate)
            else:
                listener.certificates.remove(self.certificate)
            response = self.aws_listener_certificates(operation, listener.arn, self.certificate.arn)

        self.certificate.in_use = True if operation == 'add' else False
        self.certificate.is_qualified = True if operation == 'add' else False
        self.certificate.save()

        return self.certificate

    def aws_request_certificate(self, domain, alternative_names, validation_method, idempotency_token=None):
        return self.client.request_certificate(DomainName=domain, ValidationMethod=validation_method.upper(), SubjectAlternativeNames=alternative_names, IdempotencyToken=idempotency_token)

    def aws_describe_certificate(self, arn):
        return self.client.describe_certificate(CertificateArn=arn)

    def aws_delete_certificate(self, arn):
        return self.client.delete_certificate(CertificateArn=arn)

    def aws_resend_validation_email(self, arn, domain):
        return self.client.resend_validation_email(CertificateArn=arn, Domain=domain, ValidationDomain=domain)

    def aws_list_certificates(self):
        return self.client.list_certificates()

    def aws_listener_certificates(self, operation, listener_arn, certificate_arn):
        client = boto3.client('elbv2', aws_access_key_id=settings.ACM_AWS_ACCESS_KEY_ID, aws_secret_access_key=settings.ACM_AWS_SECRET_ACCESS_KEY, region_name=settings.ACM_AWS_REGION)
        if operation == 'add':
            return client.add_listener_certificates(ListenerArn=listener_arn, Certificates=[{'CertificateArn': certificate_arn}])
        if operation == 'remove':
            return client.remove_listener_certificates(ListenerArn=listener_arn, Certificates=[{'CertificateArn': certificate_arn}])
