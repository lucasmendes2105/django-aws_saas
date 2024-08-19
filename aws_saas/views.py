from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from .services.ses_email_event import AwsSesEmailEvent

# Create your views here.


@csrf_exempt
def aws_ses_sns(request, token):
    AwsSesEmailEvent(request, token).run()
    return HttpResponse()
