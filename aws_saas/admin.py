from django.contrib import admin, messages
from django.core import management
from django.http import HttpResponse, JsonResponse
from django.utils.safestring import mark_safe
from django.shortcuts import redirect
from django.db import transaction as transaction_db
from django.conf import settings
from django.urls import reverse, path
from django.utils.html import format_html
from .models import Certificate, CertificateDomain, LoadBalancer, LoadBalancerListener, SesEmailIdentity, SesEmailEvent
from .services.acm_request_certificate import ACMRequestCertificate
from .services.ses_email_identity import AwsSesEmailIdentity
from .services.ses_util import RECIPIENT_STATUS
from io import StringIO
import pdb
import json

# Register your models here.


class CertificateDomainInline(admin.TabularInline):
    model = CertificateDomain
    readonly_fields = ('status', 'type', 'cname_name', 'cname_value', 'emails')
    min_num = 1
    extra = 0


class CertificateAdmin(admin.ModelAdmin):
    model = Certificate
    list_display = ('certificate_id', 'domains', 'status', 'in_use', 'is_qualified', 'btn_aws_acm')
    search_fields = ('certificate_id', 'certificatedomain__domain')
    list_filter = ('in_use', 'is_qualified', 'status')
    inlines = [CertificateDomainInline, ]
    actions = None

    def get_fields(self, request, obj=None):
        if not obj:
            return ('validation_method',)
        return super().get_fields(request, obj)

    def domains(self, obj):
        return ', '.join([str(i) for i in obj.certificatedomain_set.all()])

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('certificatedomain_set')

    def save_model(self, request, obj, form, change):
        if change == False:
            obj.certificate_id = 'waiting...'
            obj.domain = 'n/a'
            obj.status = 'waiting'
            obj.arn = ''
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        instances = formset.save()
        for instance in instances:
            instance.certificate.domain = instance.domain
            instance.certificate.save(update_fields=['domain', ])
            break

    def has_delete_permission(self, request, obj=None):
        if obj and obj.in_use:
            return False
        if obj and obj.domain in settings.ACM_AWS_PROTECTED_DOMAINS:
            return False
        return super().has_delete_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        if obj and obj.id:
            return False
        return super().has_change_permission(request, obj)

    def delete_model(self, request, obj):
        if obj.arn is not None and obj.arn != '':
            acm = ACMRequestCertificate(certificate=obj)
            result = acm.aws_delete_certificate(obj.arn)
        obj.delete()

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('acm-request-certificate/<pk>/', self.admin_site.admin_view(self.acm_request_certificate), name='acm_request_certificate'),
            path('acm-update-data/<pk>/', self.admin_site.admin_view(self.acm_update_data), name='acm_update_data'),
            path('acm-describe-certificate/<pk>/', self.admin_site.admin_view(self.acm_describe_certificate), name='acm_describe_certificate'),
            path('acm-certificate-listeners/<pk>/<operation>/', self.admin_site.admin_view(self.acm_certificate_listeners), name='acm_certificate_listeners'),
            path('acm-sync-certificates/', self.admin_site.admin_view(self.acm_sync_certificates), name='acm_sync_certificates'),
        ]
        return my_urls + urls

    def btn_aws_acm(self, obj):
        btns = []
        if obj.status == 'waiting':
            return format_html('<a href="{}">ACM Request</a>'.format(reverse("admin:acm_request_certificate", args=(obj.id, ))))

        btns.append('<a href="{}">Atualizar Dados</a>'.format(reverse("admin:acm_update_data", args=(obj.id, ))))

        if obj.domain not in settings.ACM_AWS_PROTECTED_DOMAINS:
            if obj.status == 'ISSUED' and obj.in_use == False:
                btns.append('<a href="{}">Plug Listeners</a>'.format(reverse("admin:acm_certificate_listeners", args=(obj.id, 'add'))))
            if obj.status == 'ISSUED' and obj.in_use == True:
                btns.append('<a href="{}">Unplug Listeners</a>'.format(reverse("admin:acm_certificate_listeners", args=(obj.id, 'remove'))))
        return format_html(' - '.join(btns))
    btn_aws_acm.short_description = 'AWS ACM'

    def acm_request_certificate(self, request, pk):
        obj = self.get_object(request, object_id=pk)

        acm = ACMRequestCertificate(certificate=obj)
        result = acm.request()

        if result:
            messages.success(request, "AWS: Certificado requisitado com sucesso!")
        else:
            messages.error(request, "AWS: Ocorreu algum erro ao solicitar o certificado.")

        return redirect(reverse('admin:aws_saas_certificate_changelist'))

    def acm_update_data(self, request, pk):
        obj = self.get_object(request, object_id=pk)

        acm = ACMRequestCertificate(certificate=obj)
        result = acm.update_data()

        if result:
            messages.success(request, format_html("AWS: Dados atualizado com sucesso! <a href='{}' target='_blank'>Describe Certificate</a>".format(reverse('admin:acm_describe_certificate', args=(obj.id,)))))
        else:
            messages.error(request, "AWS: Ocorreu um erro ao atualizar os dados.")

        return redirect(reverse('admin:aws_saas_certificate_changelist'))

    def acm_describe_certificate(self, request, pk):
        obj = self.get_object(request, object_id=pk)

        acm = ACMRequestCertificate(certificate=obj)
        result = acm.aws_describe_certificate(arn=obj.arn)

        response_data = json.dumps(result, indent=4, default=str)

        return HttpResponse(mark_safe('<pre style="font-family:monospace">{}</pre>'.format(response_data)))

    def acm_certificate_listeners(self, request, pk, operation):
        obj = self.get_object(request, object_id=pk)

        acm = ACMRequestCertificate(certificate=obj)
        result = acm.certificate_listeners(operation)

        if result:
            msg = 'AWS: Listener associado com sucesso!' if operation == 'add' else 'AWS: Listener desassociado com sucesso!'
            messages.success(request, format_html("{} <a href='{}' target='_blank'>Describe Certificate</a>".format(msg, reverse('admin:acm_describe_certificate', args=(obj.id,)))))

        return redirect(reverse('admin:aws_saas_certificate_changelist'))

    def acm_sync_certificates(self, request):
        stdout = StringIO()
        management.call_command('acm_sync_certificates', stdout=stdout)
        messages.info(request, stdout.getvalue())
        return redirect(reverse('admin:aws_saas_certificate_changelist'))


class LoadBalancerAdmin(admin.ModelAdmin):
    model = LoadBalancer
    list_display = ('name', 'arn')


class LoadBalancerListenerAdmin(admin.ModelAdmin):
    model = LoadBalancerListener
    list_display = ('load_balancer', 'arn')
    filter_horizontal = ('certificates',)


class SesEmailIdentityAdmin(admin.ModelAdmin):
    model = SesEmailIdentity
    list_display = ('identity', 'type', 'sending_enabled', 'btn_aws_ses')
    search_fields = ('identity',)
    list_filter = ('sending_enabled', 'type')
    actions = None

    def get_fields(self, request, obj=None):
        if not obj:
            return ('type', 'identity')
        return super().get_fields(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and obj.identity in settings.SES_AWS_PROTECTED_IDENTITIES:
            return False
        return super().has_delete_permission(request, obj)

    def delete_model(self, request, obj):
        ses = AwsSesEmailIdentity(email_identity=obj)
        result = ses.delete()
        obj.delete()

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if change == False:
            ses = AwsSesEmailIdentity(email_identity=obj)
            result = ses.create()

    def btn_aws_ses(self, obj):
        btns = []
        btns.append('<a href="{}">Atualizar Dados</a>'.format(reverse("admin:ses_update_email_data", args=(obj.id, ))))
        return format_html(' - '.join(btns))
    btn_aws_ses.short_description = 'AWS SES'

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('ses-update-email-data/<pk>/', self.admin_site.admin_view(self.ses_update_email_data), name='ses_update_email_data'),
            path('ses-sync-identities/', self.admin_site.admin_view(self.ses_sync_identities), name='ses_sync_identities'),
        ]
        return my_urls + urls

    def ses_update_email_data(self, request, pk):
        obj = self.get_object(request, object_id=pk)

        ses = AwsSesEmailIdentity(email_identity=obj)
        email_identity = ses.update_email_data()

        if email_identity.sending_enabled:
            messages.success(request, "SES - Dados atualizados com sucesso.")
        else:
            messages.warning(request, "SES - Dados atualizados com sucesso.")

        return redirect(reverse('admin:aws_saas_sesemailidentity_changelist'))

    def ses_sync_identities(self, request):
        stdout = StringIO()
        management.call_command('ses_sync_identities', stdout=stdout)
        messages.info(request, stdout.getvalue())
        return redirect(reverse('admin:aws_saas_sesemailidentity_changelist'))


class SesEmailEventAdmin(admin.ModelAdmin):
    model = SesEmailEvent
    list_display = ('created_at_short', 'email', 'event_type', 'bounce_type', 'bounce_sub_type', 'recipient_status_display', 'complaint_feedback_type', 'reject_reason', 'status')
    list_display_links = None
    list_filter = ('event_type', 'bounce_type', 'bounce_sub_type', 'status', 'recipient_status')
    search_fields = ('email',)

    @admin.display(description='Data cadastro', ordering='created_at')
    def created_at_short(self, obj):
        return obj.created_at.strftime("%d/%m/%y %H:%M")

    @admin.display(description='Recipient Status', ordering='recipient_status')
    def recipient_status_display(self, obj):
        status_dict = RECIPIENT_STATUS.get(obj.recipient_status) or {}
        return format_html("<a href='javascript:;' onclick='showDescription(\"{}\")'>{} - {}</a>".format(obj.recipient_status, obj.recipient_status, status_dict.get('title')))

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['recipient_status_list'] = RECIPIENT_STATUS
        return super().changelist_view(request, extra_context=extra_context)
