from django.db import models

# Create your models here.


class Certificate(models.Model):
    certificate_id = models.CharField(max_length=255)
    domain = models.CharField(max_length=255)
    status = models.CharField(max_length=50)
    in_use = models.BooleanField(default=False)
    is_qualified = models.BooleanField(default=False)
    validation_method = models.CharField(max_length=20, default='dns', choices=(('dns', 'DNS'), ('email', 'E-mail')))
    arn = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    issued_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.domain


class CertificateDomain(models.Model):
    certificate = models.ForeignKey(Certificate, on_delete=models.CASCADE)
    domain = models.CharField(max_length=255)
    status = models.CharField(max_length=50)
    type = models.CharField(max_length=50)
    cname_name = models.CharField(max_length=255, null=True, blank=True)
    cname_value = models.CharField(max_length=255, null=True, blank=True)
    emails = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.domain


class LoadBalancer(models.Model):
    name = models.CharField(max_length=255)
    arn = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class LoadBalancerListener(models.Model):
    load_balancer = models.ForeignKey(LoadBalancer, on_delete=models.PROTECT)
    arn = models.CharField(max_length=255)
    certificates = models.ManyToManyField(Certificate, verbose_name='Certificados', blank=True)

    def __str__(self):
        return self.arn


class SesEmailIdentity(models.Model):
    type = models.CharField(max_length=20, default='email_address', choices=(('email_address', 'E-mail'), ('domain', 'Domínio')))
    identity = models.CharField(max_length=255)
    sending_enabled = models.BooleanField(default=False)

    def __str__(self):
        return self.identity


class SesEmailEvent(models.Model):
    EVENT_TYPE_CHOICES = (('Bounce', 'Bounce'), ('Complaint', 'Complaint'), ('Delivery', 'Delivery'), ('Send', 'Send'), ('Reject', 'Reject'), ('Open', 'Open'), ('Click', 'Click'), ('RenderingFailure', 'Rendering Failure'), ('DeliveryDelay', 'DeliveryDelay'), ('Subscription', 'Subscription'))
    BOUNCE_TYPE_CHOICES = (('Permanent', 'Permanent'), ('Transient', 'Transient'), ('Undetermined', 'Undetermined'))
    BOUNCE_SUB_TYPE_CHOICES = (('Undetermined', 'Undetermined'), ('General', 'General'), ('NoEmail', 'NoEmail'), ('Suppressed', 'Suppressed'), ('OnAccountSuppressionList', 'OnAccountSuppressionList'), ('MailboxFull', 'MailboxFull'), ('MessageTooLarge', 'MessageTooLarge'), ('ContentRejected', 'ContentRejected'), ('AttachmentRejected', 'AttachmentRejected'))
    STATUS_CHOICES = (('new', 'new'), ('finished', 'finished'))

    email = models.EmailField()
    event_type = models.CharField(max_length=20, choices=EVENT_TYPE_CHOICES)
    bounce_type = models.CharField(max_length=20, null=True, choices=BOUNCE_TYPE_CHOICES)
    bounce_sub_type = models.CharField(max_length=30, null=True, choices=BOUNCE_SUB_TYPE_CHOICES)
    complaint_feedback_type = models.CharField(max_length=30, null=True)
    reject_reason = models.CharField(max_length=155, null=True)
    recipient_status = models.CharField(max_length=10, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default='new', choices=STATUS_CHOICES)

    def __str__(self):
        return self.email

    class Meta:
        indexes = [
            models.Index(fields=['status', 'event_type', 'bounce_type']),
        ]
