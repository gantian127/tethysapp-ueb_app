import json
import xmltodict
from oauthlib.oauth2 import TokenExpiredError

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from tethys_sdk.gizmos import TextInput, SelectInput,DatePicker, GoogleMapView

from hs_restclient import HydroShare, HydroShareAuthOAuth2, HydroShareNotAuthorized, HydroShareNotFound

from epsg_list import EPSG_List
from model_run_utils import *
from model_input_utils import *
from user_settings import *


# home page views
@login_required()
def home(request):
    """
    Controller for the app home page.
    """
    res_id = request.GET.get('res_id', None)
    context = {'res_id': res_id}

    return render(request, 'ueb_app/home.html', context)


# model input views and ajax submit
@login_required()
def model_input(request):

    # bounding box
    north_lat = TextInput(display_text='North Latitude',
                          name='north_lat',
                          attributes={'required': True}
                          )

    south_lat = TextInput(display_text='South Latitude',
                          name='south_lat',
                          attributes={'required': True}
                          )

    west_lon = TextInput(display_text='West Longitude',
                         name='west_lon',
                         attributes={'required': True}
                          )

    east_lon = TextInput(display_text='East Longitude',
                         name='east_lon',
                         attributes={'required': True}
                         )

    # outlet point
    outlet_x = TextInput(display_text='Point Longitude',
                       name='outlet_x',
                       attributes={'required': True}
                       )

    outlet_y = TextInput(display_text='Point Latitude',
                       name='outlet_y',
                       attributes={'required': True}
                       )

    # wathershed name and threshold
    watershed_name = TextInput(
                       # display_text='Watershed Name',
                       name='watershed_name',
                       initial='my watershed',
                       attributes={'style': 'width:350px'}
                       )

    stream_threshold = TextInput(
                       # display_text='Stream Threshold',
                       name='stream_threshold',
                       initial='1000',
                       attributes={'style': 'width:350px'}
                       )

    # epsg code
    epsg_code = SelectInput(display_text='',
                            name='epsg_code',
                            multiple=False,
                            options=EPSG_List,
                            initial=['5072 : NAD83(NSRS2007) / Conus Albers'],
                            attributes={'style': 'width:200px', 'required': True}
                            )

    # time period
    start_time = DatePicker(name='start_time',
                         display_text='Start Date',
                         autoclose=True,
                         format='yyyy/mm/dd',
                         today_button=True,
                         multidate='1',
                         attributes={'required': True}
                        )

    end_time = DatePicker(name='end_time',
                            display_text='End Date',
                            autoclose=True,
                            format='yyyy/mm/dd',
                            today_button=True,
                            multidate='1',
                            attributes={'required': True}
                            )

    # model resolution
    x_size = TextInput(display_text='X size(m)',
                       name='x_size',
                       attributes={'required': True}
                       )

    y_size = TextInput(display_text='Y size(m)',
                       name='y_size',
                       attributes={'required': True}
                       )

    dx_size = TextInput(display_text='dX size(m)',
                       name='dx_size',
                       attributes={'required': True}
                       )

    dy_size = TextInput(display_text='dY size(m)',
                        name='dy_size',
                        attributes={'required': True}
                        )

    # resource info
    res_title = TextInput(display_text='HydroShare resource title',
                       name='res_title',
                       placeholder='The title should include at least 5 characters',
                       attributes={'style': 'width:350px', 'required': True}
                       )
    res_keywords = TextInput(display_text='HydroShare resource keywords',
                       name='res_keywords',
                       placeholder='e.g. keyword1, keyword2',
                       attributes={'style': 'width:350px', 'required': True}
                       )
    # context
    context = {'north_lat': north_lat,
               'south_lat': south_lat,
               'west_lon': west_lon,
               'east_lon': east_lon,
               'outlet_x': outlet_x,
               'outlet_y': outlet_y,
               'watershed_name': watershed_name,
               'stream_threshold': stream_threshold,
               'epsg_code': epsg_code,
               'start_time': start_time,
               'end_time': end_time,
               'x_size': x_size,
               'y_size': y_size,
               'dx_size': dx_size,
               'dy_size': dy_size,
               'res_title': res_title,
               'res_keywords': res_keywords,
               }

    return render(request, 'ueb_app/model_input.html', context)


@login_required()
def model_input_submit(request):
    # TODO: pass the token, client id, client secret to HydroDS to create new resource in HydroShare
    ajax_response = {}

    if request.is_ajax and request.method == 'POST':

        validation = validate_model_input_form(request)

        if validation['is_valid']:
            model_input_job = submit_model_input_job(validation['result'])
            ajax_response = model_input_job
        else:
            ajax_response['status'] = 'Error'
            ajax_response['result'] = ' '.join(validation['result'].values())

    else:
        ajax_response['status'] = 'Error'
        ajax_response['result'] = 'Please verify that the request is ajax call with post method'

    return HttpResponse(json.dumps(ajax_response))


# model run views and ajax submit
@login_required()
def model_run(request):
    try:
        # authentication:
        OAuthHS = get_OAuthHS(request)

        # get user editable model instance resource list
        hs = OAuthHS['hs']
        hs_editable_res_name_list = []

        for resource in hs.getResourceList(owner=OAuthHS.get('user_name'), types=["ModelInstanceResource"]):
            hs_editable_res_name_list.append((resource['resource_title'], resource['resource_id']))

        # get the initial list item
        res_id = request.GET.get('res_id', None)
        if res_id:
            initial = [option[0] for option in hs_editable_res_name_list if option[1] == res_id]
        else:
            initial = [hs_editable_res_name_list[0][0]]

        options = hs_editable_res_name_list if hs_editable_res_name_list else [('No model instance resource is available', '')]

    except Exception:
        options = [('Failed to retrieve the model instance resources list', '')]
        initial = ['Failed to retrieve the model instance resources list']

    finally:
        # resource list
        resource_list = SelectInput(
                                name='resource_list',
                                multiple=False,
                                options=options,
                                attributes={'style': 'width:200px', 'required': True},
                                initial=initial,
                                )

        # context
        context = {'resource_list': resource_list,
                   'user_name': OAuthHS.get('user_name')}

    return render(request, 'ueb_app/model_run.html', context)


@login_required()
def model_run_load_metadata(request):

    try:
        # authentication
        OAuthHS = get_OAuthHS(request)

        if OAuthHS.get('hs'):
            # retrieve metadata dict and resource id
            res_id = request.POST['resource_list']
            md_dict = xmltodict.parse(OAuthHS.get('hs').getScienceMetadata(res_id))

            # retrieve bounding box
            north_lat = 'unknown'
            south_lat = 'unknown'
            east_lon = 'unknown'
            west_lon = 'unknown'
            start_time = 'unknown'
            end_time = 'unknown'

            cov_dict = md_dict['rdf:RDF']['rdf:Description'][0].get('dc:coverage')
            if cov_dict:
                for item in cov_dict:
                    if 'dcterms:box' in item.keys():
                        bounding_box_list = item['dcterms:box']['rdf:value'].split(';')
                        for item in bounding_box_list:
                            if 'northlimit' in item:
                                north_lat = item.split('=')[1]
                            elif 'southlimit' in item:
                                south_lat = item.split('=')[1]
                            elif 'eastlimit' in item:
                                east_lon = item.split('=')[1]
                            elif 'westlimit' in item:
                                west_lon = item.split('=')[1]

                    elif 'dcterms:period' in item.keys():
                        time_list = item['dcterms:period']['rdf:value'].split(';')
                        for item in time_list:
                            if 'start' in item:
                                start_time = item.split('=')[1]
                                start_time = start_time.split('T')[0]
                            elif 'end' in item:
                                end_time = item.split('=')[1]
                                end_time = end_time.split('T')[0]

            status = 'Success'
            result = {
                'res_id': res_id,
                'north_lat': north_lat,
                'south_lat': south_lat,
                'east_lon': east_lon,
                'west_lon': west_lon,
                'outlet_x': '-109.9',
                'outlet_y': '43.3',
                'outlet_point': 'unknown',
                'start_time': start_time,
                'end_time': end_time,
                'cell_x_size': 'unknown',
                'cell_y_size': 'unknown',
                'epsg_code': 'unknown',

            }

        else:
            status = 'Error'
            result = OAuthHS.get('error')

    except Exception as e:
        status = 'Error'
        result = 'Failed to retrieve the model instance resource metadata. ' + e.message

    finally:
        ajax_response = {
            'status': status,
            'result': result
        }

    return HttpResponse(json.dumps(ajax_response))


@login_required()
def model_run_submit_execution(request):
    if request.is_ajax and request.method == 'POST':
        res_id = request.POST['resource_list']
        OAuthHS = get_OAuthHS(request)
        if 'error' in OAuthHS.keys():
            ajax_response = {
                'status': 'Error',
                'result': OAuthHS['error']
            }

        else:
            ajax_response = submit_model_run_job(res_id, OAuthHS, hydrods_name, hydrods_password)

    else:
        ajax_response = {
            'status': 'Error',
            'result': 'Please verify that the request is ajax call with post method'
        }

    return HttpResponse(json.dumps(ajax_response))


# check status views and ajax submit
@login_required
def check_status(request):
    # job_id
    job_id = TextInput(display_text='',
                       name='job_id',
                       placeholder='Enter the Job ID Here',
                       attributes={'required': True, 'style': 'width:800px;height:41px'}
                          )

    context = {'job_id': job_id}

    return render(request, 'ueb_app/check_status.html', context)


# help views
@login_required
def help_page(request):
    context = {}

    return render(request, 'ueb_app/help.html', context)


# get hs object through oauth
def get_OAuthHS(request):
    OAuthHS = {}

    try:
        hs_hostname = "www.hydroshare.org"

        client_id = getattr(settings, "SOCIAL_AUTH_HYDROSHARE_KEY", None)
        client_secret = getattr(settings, "SOCIAL_AUTH_HYDROSHARE_SECRET", None)

        # this line will throw out from django.core.exceptions.ObjectDoesNotExist if current user is not signed in via HydroShare OAuth
        token = request.user.social_auth.get(provider='hydroshare').extra_data['token_dict']
        user_name = request.user.social_auth.get(provider='hydroshare').uid

        auth = HydroShareAuthOAuth2(client_id, client_secret, token=token)
        hs = HydroShare(auth=auth, hostname=hs_hostname)

        OAuthHS['hs'] = hs
        OAuthHS['token'] = token
        OAuthHS['client_id'] = client_id
        OAuthHS['client_secret'] = client_secret
        OAuthHS['user_name'] = user_name

    except ObjectDoesNotExist as e:
        OAuthHS['error'] = 'ObjectDoesNotExist: ' + e.message
    except TokenExpiredError as e:
        OAuthHS['error'] = 'TokenExpiredError ' + e.message
    except HydroShareNotAuthorized as e:
        OAuthHS['error'] = 'HydroShareNotAuthorized' + e.message
    except HydroShareNotFound as e:
        OAuthHS['error'] = 'HydroShareNotFound' + e.message
    except Exception as e:
        OAuthHS['error'] = 'Authentication Failure:' + e.message

    return OAuthHS


# test part #
def test(request):
    """
    Controller for the app home page.
    """
    context = {}

    return render(request, 'ueb_app/test.html', context)


def test_submit(request):

    return HttpResponse(json.dumps({'name':'name'}))