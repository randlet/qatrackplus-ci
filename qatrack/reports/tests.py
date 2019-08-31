import io
import json
import time
from unittest import mock

from django.contrib.admin.sites import AdminSite
from django.contrib.sites.models import Site
from django.core import mail
from django.http import Http404
from django.test import RequestFactory, TestCase
from django.test.utils import override_settings
from django.urls import reverse
from django.utils import timezone
from django_q.models import Schedule
import pytz
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as e_c
from selenium.webdriver.support.ui import Select

# Create your tests here.
from qatrack.qa.models import Frequency, Group, TestListInstance, User
from qatrack.qa.tests import utils
from qatrack.qa.tests.test_selenium import BaseQATests
from qatrack.reports import admin, filters, forms, models, reports, tasks, views
from qatrack.units.models import Site as USite


def local_852am():
    tz = timezone.get_current_timezone()
    return tz.localize(timezone.datetime(2019, 1, 1, 8, 52))


class TestReportForm:

    def test_report_type_title_attrs_created(self):
        """ensure title attribute added to each choice"""
        form = forms.ReportForm()
        widget = form.fields['report_type'].widget
        assert 'title="%s"' % reports.QCSummaryReport.description in widget.render("name", [])


class TestSelectReport(TestCase):

    def setUp(self):

        self.url = reverse("reports")
        user = User.objects.create_superuser("user", "a@b.com", "password")
        self.client.force_login(user)

    def test_initial_get(self):
        resp = self.client.get(self.url)
        assert isinstance(resp.context['report_form'], forms.ReportForm)

    def test_invalid_report_no_report_type(self):
        data = {
            'work_completed': '01 Jan 2000 - 01 Feb 2000',
        }
        resp = self.client.post(self.url, data)
        assert 'report_format' in resp.context['report_form'].errors
        assert resp.context['filter_form'] is None

    def test_invalid_report_valid_filter(self):
        data = {
            'root-report_type': 'qc-summary-by-date',
            'root-report_format': None,
            'work_completed': '01 Jan 2000 - 01 Feb 2000',
        }
        resp = self.client.post(self.url, data)
        assert 'report_format' in resp.context['report_form'].errors
        assert len(resp.context['filter_form'].errors) == 0

    def test_invalid_report_invalid_filter(self):
        data = {
            'root-report_type': 'qc-summary-by-date',
            'root-report_format': None,
            'work_completed': '',
        }
        resp = self.client.post(self.url, data)
        assert 'report_format' in resp.context['report_form'].errors
        assert 'work_completed' in resp.context['filter_form'].errors

    def test_valid_report_valid_filter(self):
        data = {
            'root-report_type': 'qc-summary-by-date',
            'root-title': 'Title',
            'root-report_format': 'pdf',
            'root-include_signature': True,
            'work_completed': '01 Jan 2000 - 01 Feb 2000',
        }
        resp = self.client.post(self.url, data)
        # everything valid, so this should be report rendering context now, rather than forms
        assert 'report_details' in resp.context

    def test_no_perms(self):
        user = User.objects.create_user("reg_user", "a@b.com", "password")
        self.client.force_login(user)
        resp = self.client.post(self.url, {})
        assert resp.status_code == 403


class TestReportPreview(TestCase):

    def setUp(self):
        self.url = reverse("reports-preview")
        user = User.objects.create_superuser("user", "a@b.com", "password")
        self.client.force_login(user)

    def test_form_invalid_with_report_type(self):
        """Invalid base form so should get errors"""
        data = {
            'root-report_type': 'qc-summary-by-date',
            'work_completed': '01 Jan 2000 - 01 Feb 2000',
        }
        payload = self.client.post(self.url, data).json()
        assert payload['errors']
        assert 'report_format' in payload['base_errors']
        assert payload['preview'] == ''

    def test_form_valid_with_invalid_report_form(self):
        """Invalid base form so should get errors"""
        data = {
            'root-report_type': 'qc-summary-by-date',
            'root-title': 'Title',
            'root-report_format': 'pdf',
            'root-include_signature': True,
            'work_completed': '01 Jan 2000',
        }
        payload = self.client.post(self.url, data).json()
        assert payload['errors']
        assert payload['base_errors'] == {}
        assert 'work_completed' in payload['report_errors']

    def test_form_valid_with_valid_report_form(self):
        """Invalid base form so should get errors"""
        data = {
            'root-report_type': 'qc-summary-by-date',
            'root-title': 'Title',
            'root-report_format': 'pdf',
            'root-include_signature': True,
            'work_completed': '01 Jan 2000 - 01 Feb 2000',
        }
        payload = self.client.post(self.url, data).json()
        assert not payload['errors']
        assert '<div' in payload['preview']

    def test_no_perms(self):
        user = User.objects.create_user("reg_user", "a@b.com", "password")
        self.client.force_login(user)
        resp = self.client.post(self.url, {})
        assert resp.status_code == 403


class TestSaveReport(TestCase):

    def setUp(self):
        self.url = reverse("reports-save")
        user = User.objects.create_superuser("user", "a@b.com", "password")
        self.client.force_login(user)

    def test_form_invalid_with_report_type(self):
        """Invalid base form so should get errors"""
        data = {
            'root-report_type': 'qc-summary-by-date',
            'work_completed': '01 Jan 2000 - 01 Feb 2000',
        }
        payload = self.client.post(self.url, data).json()
        assert payload['errors']
        assert 'report_format' in payload['base_errors']

    def test_form_valid_with_invalid_report_form(self):
        """Invalid base form so should get errors"""
        data = {
            'root-report_type': 'qc-summary-by-date',
            'root-title': 'Title',
            'root-report_format': 'pdf',
            'root-include_signature': True,
            'work_completed': '01 Jan 2000',
        }
        payload = self.client.post(self.url, data).json()
        assert payload['errors']
        assert payload['base_errors'] == {}
        assert 'work_completed' in payload['report_errors']

    def test_form_valid_with_valid_report_form(self):
        """Invalid base form so should get errors"""
        data = {
            'root-report_type': 'qc-summary-by-date',
            'root-title': 'Title',
            'root-report_format': 'pdf',
            'root-include_signature': True,
            'work_completed': '01 Jan 2000 - 01 Feb 2000',
        }
        assert models.SavedReport.objects.count() == 0
        payload = self.client.post(self.url, data).json()
        assert models.SavedReport.objects.count() == 1
        assert not payload['errors']
        assert 'report_id' in payload
        assert 'success_message' in payload

    def test_update_report(self):
        """Invalid base form so should get errors"""
        data = {
            'root-report_type': 'qc-summary-by-date',
            'root-title': 'Title',
            'root-report_format': 'pdf',
            'root-include_signature': True,
            'work_completed': '01 Jan 2000 - 01 Feb 2000',
        }
        self.client.post(self.url, data).json()
        sr = models.SavedReport.objects.first()
        assert sr.report_format == "pdf"
        data['report_id'] = sr.id
        data['root-report_format'] = "csv"
        self.client.post(self.url, data).json()
        sr.refresh_from_db()
        assert models.SavedReport.objects.count() == 1
        assert sr.report_format == "csv"

    def test_no_perms(self):
        user = User.objects.create_user("reg_user", "a@b.com", "password")
        self.client.force_login(user)
        resp = self.client.post(self.url, {})
        assert resp.status_code == 403

    def test_no_edit_perms(self):
        user = User.objects.create_user("reg_user", "a@b.com", "password")
        data = {
            'root-report_type': 'qc-summary-by-date',
            'root-title': 'Title',
            'root-report_format': 'pdf',
            'root-include_signature': True,
            'work_completed': '01 Jan 2000 - 01 Feb 2000',
        }
        self.client.post(self.url, data).json()
        sr = models.SavedReport.objects.first()
        sr.created_by = user
        sr.save()
        data = {
            'root-title': 'Title 2',
            'report_id': sr.id,
        }
        resp = self.client.post(self.url, data)
        assert resp.status_code == 403


class TestLoadReport(TestCase):

    def setUp(self):
        self.url = reverse("reports-load")
        self.user = User.objects.create_superuser("user", "a@b.com", "password")
        self.client.force_login(self.user)

    def test_report_not_found(self):
        """Invalid base form so should get errors"""
        payload = self.client.get(self.url, {'report_id': 1}).json()
        assert payload['errors']

    def test_report_loaded(self):
        """Invalid base form so should get errors"""
        sr = models.SavedReport.objects.create(
            report_type=reports.QCSummaryReport.report_type,
            report_format="pdf",
            title="title",
            filters={},
            created_by=self.user,
            modified_by=self.user,
        )
        payload = self.client.get(self.url, {'report_id': sr.id}).json()
        assert not payload['errors']
        assert payload['id'] == str(sr.id)
        assert 'fields' in payload

    def test_no_perms(self):
        user = User.objects.create_user("reg_user", "a@b.com", "password")
        self.client.force_login(user)
        resp = self.client.post(self.url, {})
        assert resp.status_code == 403


class TestDeleteReport(TestCase):

    def setUp(self):
        self.url = reverse("reports-delete")
        self.user = User.objects.create_superuser("user", "a@b.com", "password")
        self.client.force_login(self.user)

    def test_report_not_found(self):
        """Invalid base form so should get errors"""
        payload = self.client.post(self.url, {'report_id': 1}).json()
        assert payload['errors']
        assert not payload['deleted']

    def test_report_deleted(self):
        """Invalid base form so should get errors"""
        sr = models.SavedReport.objects.create(
            report_type=reports.QCSummaryReport.report_type,
            report_format="pdf",
            title="title",
            filters={},
            created_by=self.user,
            modified_by=self.user,
        )
        payload = self.client.post(self.url, {'report_id': sr.id}).json()
        assert not payload['errors']
        assert payload['deleted']

    def test_no_perms(self):
        user = User.objects.create_user("reg_user", "a@b.com", "password")
        self.client.force_login(user)
        resp = self.client.post(self.url, {})
        assert resp.status_code == 403


class TestScheduleReport(TestCase):

    def setUp(self):
        self.url = reverse("reports-schedule")
        self.user = User.objects.create_superuser("user", "a@b.com", "password")
        self.client.force_login(self.user)

    def test_report_scheduled(self):
        """Report scheduled"""
        sr = models.SavedReport.objects.create(
            report_type=reports.QCSummaryReport.report_type,
            report_format="pdf",
            title="title",
            filters={},
            created_by=self.user,
            modified_by=self.user,
        )
        self.user.first_name = "First"
        self.user.last_name = "Last"
        self.user.save()

        rec = "RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE"
        data = {
            'schedule-report': sr.id,
            'schedule-schedule': rec,
            'schedule-time': '00:00:00',
            'schedule-emails': 'b@c.com',
            'schedule-users': [self.user.pk],
        }
        payload = self.client.post(self.url, data).json()
        assert not payload['error']
        assert payload['message'] == "Schedule updated successfully!"
        assert set(models.ReportSchedule.objects.first().recipients()) == set(['"First Last"<a@b.com>', "b@c.com"])

    def test_missing_recipients(self):
        """Report scheduled"""
        sr = models.SavedReport.objects.create(
            report_type=reports.QCSummaryReport.report_type,
            report_format="pdf",
            title="title",
            filters={},
            created_by=self.user,
            modified_by=self.user,
        )
        rec = "RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE"
        data = {
            'schedule-report': sr.id,
            'schedule-schedule': rec,
            'schedule-time': '00:00:00',
        }
        payload = self.client.post(self.url, data).json()
        assert payload['error']
        assert payload['message'] == ""

    def test_no_perms(self):
        user = User.objects.create_user("reg_user", "a@b.com", "password")
        self.client.force_login(user)
        resp = self.client.post(self.url, {})
        assert resp.status_code == 403

    def test_not_editable(self):
        user = User.objects.create_user("reg_user", "a@b.com", "password")
        sr = models.SavedReport.objects.create(
            report_type=reports.QCSummaryReport.report_type,
            report_format="pdf",
            title="title",
            filters={},
            created_by=user,
            modified_by=user,
        )
        rec = "RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE"
        data = {
            'schedule-report': sr.id,
            'schedule-schedule': rec,
            'schedule-time': '00:00:00',
        }
        resp = self.client.post(self.url, data)
        assert resp.status_code == 403


class TestDeleteSchedule(TestCase):

    def setUp(self):
        self.url = reverse("reports-schedule-delete")
        self.user = User.objects.create_superuser("user", "a@b.com", "password")
        self.client.force_login(self.user)
        self.sr = models.SavedReport.objects.create(
            report_type=reports.QCSummaryReport.report_type,
            report_format="pdf",
            title="title",
            filters={},
            created_by=self.user,
            modified_by=self.user,
        )
        rec = "RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE"
        models.ReportSchedule.objects.create(
            report=self.sr,
            time="00:00:00",
            schedule=rec,
            created_by=self.user,
            modified_by=self.user,
        )

    def test_report_schedule_cleared(self):

        payload = self.client.post(self.url, {'schedule-report': self.sr.id}).json()
        assert not payload['error']
        assert payload['message'] == "Schedule cleared"
        assert models.ReportSchedule.objects.count() == 0

    def test_no_schedule(self):
        self.sr.schedule.delete()
        payload = self.client.post(self.url, {'schedule-report': self.sr.id}).json()
        assert not payload['error']
        assert payload['message'] == "Schedule cleared"

    def test_no_perms(self):
        user = User.objects.create_user("reg_user", "a@b.com", "password")
        self.client.force_login(user)
        resp = self.client.post(self.url, {'schedule-report': self.sr.id})
        assert resp.status_code == 403

    def test_not_editable(self):
        user = User.objects.create_user("reg_user", "a@b.com", "password")
        self.sr.schedule.created_by = user
        self.sr.schedule.save()
        resp = self.client.post(self.url, {'schedule-report': self.sr.id})
        assert resp.status_code == 403


class TestFilters(TestCase):

    def setUp(self):

        self.factory = RequestFactory()
        self.url = reverse("reports-filter")

    def test_valid_get_filter(self):
        req = self.factory.get(self.url, data={'report_type': 'qc-summary-by-date'})
        resp = views.get_filter(req)
        assert json.loads(resp.content.decode())

    def test_invalid_get_filter(self):
        req = self.factory.get(self.url, data={'report_type': 'unknown'})
        with self.assertRaises(Http404):
            views.get_filter(req)

    def test_customdaterangefield_dashes(self):
        cdf = filters.CustomDateRangeField()
        test_inputs = [
            "2019-01-01 - 2019-01-02",
            "2019-01-01-2019-01-02",
            "1 Jan 2019 - 2 Jan 2019",
            "1 Jan 2019-2 Jan 2019",
        ]
        for test_input in test_inputs:
            start, end = cdf.clean(test_input)
            tz = timezone.get_current_timezone()
            expected_start = tz.localize(timezone.datetime(2019, 1, 1))
            expected_end = tz.localize(timezone.datetime(2019, 1, 2, 23, 59, 59))
            assert (start, end) == (expected_start, expected_end)


class TestInstanceToFormFields(TestCase):

    def setUp(self):

        u = User.objects.create_superuser("super", "a@b.com", "password")
        self.saved_report = models.SavedReport.objects.create(
            title="test report",
            report_type=reports.QCSummaryReport.report_type,
            report_format='csv',
            filters={},
            created_by=u,
            modified_by=u,
            include_signature=False,
        )

    def test_root_report_type(self):
        res = forms.serialize_savedreport(self.saved_report)
        assert res['root-report_type'] == ['select', reports.QCSummaryReport.report_type]

    def test_root_report_title(self):
        res = forms.serialize_savedreport(self.saved_report)
        assert res['root-title'] == ['text', self.saved_report.title]

    def test_root_report_format(self):
        res = forms.serialize_savedreport(self.saved_report)
        assert res['root-report_format'] == ['select', self.saved_report.report_format]

    def test_root_include_sig(self):
        res = forms.serialize_savedreport(self.saved_report)
        assert res['root-include_signature'] == ['checkbox', self.saved_report.include_signature]

    def test_root_visible_to(self):
        g = Group.objects.create(name="group")
        self.saved_report.visible_to.add(g)
        res = forms.serialize_savedreport(self.saved_report)
        assert res['root-visible_to'] == ['select', [g.pk]]

    def test_daterange(self):
        sr = models.SavedReport(report_type=reports.QCSummaryReport.report_type)
        sr.filters = {'work_completed': ["1 Jan 2019", "2 Jan 2019"]}
        res = forms.serialize_savedreport(sr)
        assert res['work_completed'] == ['text', '01 Jan 2019 - 02 Jan 2019']


class TestReportToFormFields(TestCase):

    def setUp(self):

        self.report = reports.QCSummaryReport()

    def test_daterange(self):
        report = reports.QCSummaryReport(report_opts={'work_completed': ["1 Jan 2019", "2 Jan 2019"]})
        res = forms.serialize_report(report)
        assert res['work_completed'] == ['text', '01 Jan 2019 - 02 Jan 2019']

    def test_visible_to(self):
        g = Group.objects.create(name="group")
        base_opts = {'visible_to': Group.objects.all()}
        report = reports.QCSummaryReport(base_opts=base_opts)
        res = forms.serialize_report(report)
        assert res['root-visible_to'] == ['select', [g.pk]]

    def test_root_include_sig(self):
        base_opts = {'include_signature': False}
        report = reports.QCSummaryReport(base_opts=base_opts)
        res = forms.serialize_report(report)
        assert res['root-include_signature'] == ['checkbox', False]


class TestSerializeFormData(TestCase):

    def test_queryset(self):
        """Queryset should be serialized as list of pks"""
        g = Group.objects.create(name="group")
        data = {'groups': Group.objects.all()}
        serialized = forms.serialize_form_data(data)
        assert json.loads(serialized) == {'groups': [g.pk]}

    def test_object(self):
        """Model instance should be serialized as instace pk"""
        g = Group.objects.create(name="group")
        data = {'group': g}
        serialized = forms.serialize_form_data(data)
        assert json.loads(serialized) == {'group': g.pk}

    def test_list(self):
        """iterable of objects without pk attribute should be returned as list"""
        data = {'list': ['a', 'b', 'c']}
        serialized = forms.serialize_form_data(data)
        assert json.loads(serialized) == data


class TestBaseReport(TestCase):

    def test_get_queryset(self):
        """get_queryset should return null for BaseReport"""
        assert reports.BaseReport().get_queryset() is None

    def test_get_filter_form_null(self):
        """get_filter_form should return null for BaseReport"""
        assert reports.BaseReport().get_filter_form() is None

    def test_get_template(self):
        """By default retrieve html report template"""
        t = reports.BaseReport().get_template()
        assert t.template.name == "reports/html_report.html"

    def test_get_filename(self):
        """By default filename is qatrack-report.ftype"""
        assert reports.BaseReport().get_filename("pdf") == "qatrack-report.pdf"

    def test_get_report_url(self):
        Site.objects.update(domain="example.com")
        url = reports.BaseReport().get_report_url()
        assert url == 'http://example.com/reports/?opts=%7B%7D'

    def test_plain_property(self):
        """If report.html is truthy, report.plain should be False"""
        rep = reports.BaseReport()
        rep.report_format = "csv"
        assert rep.plain is True
        assert rep.html is False

    def test_html_property(self):
        """If report.html is truthy, report.plain should be False"""
        rep = reports.BaseReport()
        rep.report_format = "html"
        assert rep.plain is False
        assert rep.html is True

    def test_make_html_url(self):
        Site.objects.update(domain="example.com")
        rep = reports.BaseReport()
        rep.report_format = "html"
        url = rep.make_url("foo/bar", text="foo", title="bar")
        assert url == '<a href="http://example.com/foo/bar" title="bar">foo</a>'

    def test_make_plain_url(self):
        Site.objects.update(domain="example.com")
        rep = reports.BaseReport()
        rep.report_format = "csv"
        url = rep.make_url("/foo/bar", text="foo", title="bar")
        assert url == 'http://example.com/foo/bar'

    def test_default_detail_value_format_none(self):
        assert reports.BaseReport().default_detail_value_format(None) == "<em>No Filter</em>"

    def test_default_detail_value_format_str(self):
        assert reports.BaseReport().default_detail_value_format("foo") == "foo"

    @override_settings(TIME_ZONE="America/Toronto")
    def test_default_detail_value_format_datetime_utc(self):
        dt = timezone.datetime(2019, 1, 2, 2, 0, tzinfo=timezone.utc)
        assert reports.BaseReport().default_detail_value_format(dt) == "01 Jan 2019"

    @override_settings(TIME_ZONE="America/Toronto")
    def test_default_detail_value_format_datetime_naive(self):
        dt = timezone.datetime(2019, 1, 2, 2, 0)
        assert reports.BaseReport().default_detail_value_format(dt) == "02 Jan 2019"

    @override_settings(TIME_ZONE="America/Toronto")
    def test_default_detail_value_format_datetime_range_utc(self):
        dt1 = timezone.datetime(2019, 1, 2, 2, 0, tzinfo=timezone.utc)
        dt2 = timezone.datetime(2019, 1, 3, 2, 0, tzinfo=timezone.utc)
        assert reports.BaseReport().default_detail_value_format([dt1, dt2]) == "01 Jan 2019 - 02 Jan 2019"

    @override_settings(TIME_ZONE="America/Toronto")
    def test_default_detail_value_format_datetime_range_naive(self):
        dt1 = timezone.datetime(2019, 1, 2, 2, 0)
        dt2 = timezone.datetime(2019, 1, 3, 2, 0)
        assert reports.BaseReport().default_detail_value_format([dt1, dt2]) == "02 Jan 2019 - 03 Jan 2019"

    def test_default_detail_value_format_iterable(self):
        assert reports.BaseReport().default_detail_value_format([1, 2]) == "1, 2"

    def test_default_detail_value_format_integer(self):
        assert reports.BaseReport().default_detail_value_format(1) == "1"

    def test_get_report_details_no_filter_set(self):
        assert reports.BaseReport().get_report_details() == []

    def test_to_html(self):
        assert 'class="container-fluid"' in reports.BaseReport().to_html()

    @mock.patch("qatrack.reports.reports.chrometopdf")
    def test_to_pdf(self, chrometopdf):
        reports.BaseReport().to_pdf()
        assert 'class="container-fluid"' in chrometopdf.call_args[0][0]

    def test_to_csv(self):
        rep = reports.BaseReport()
        rep.to_table = lambda x: [[1]]
        csv = rep.to_csv()
        assert isinstance(csv, io.StringIO)
        assert csv.tell() == 0

    def test_to_xslx(self):
        rep = reports.BaseReport()
        rep.to_table = lambda x: [[1]]
        xls = rep.to_xlsx()
        assert isinstance(xls, io.BytesIO)
        assert xls.tell() == 0


class TestQCSummaryReport(TestCase):

    def test_get_queryset(self):
        assert reports.QCSummaryReport().get_queryset().model._meta.model_name == "testlistinstance"

    def test_get_filename(self):
        assert reports.QCSummaryReport().get_filename('pdf') == 'qc-summary.pdf'

    def test_get_utc_site(self):
        site = USite.objects.create(name="site")
        sites = reports.QCSummaryReport().get_unit_test_collection__unit__site_details([site, 'null'])
        assert sites == ('Site', 'site, No Site Assigned')

    def test_get_utc_freq(self):
        freq = Frequency.objects.create(name="freq", window_start=0, window_end=0)
        freqs = reports.QCSummaryReport().get_unit_test_collection__frequency_details([freq, 'null'])
        assert freqs == ('Frequencies', 'freq, Ad Hoc')

    @override_settings(TIME_ZONE="America/Toronto")
    def test_get_work_completed_html(self):
        rep = reports.QCSummaryReport()
        rep.report_format = "html"
        tz = pytz.timezone("America/Toronto")
        work_completed = tz.localize(timezone.datetime(2019, 1, 1, 12))
        tli = utils.create_test_list_instance(work_completed=work_completed)
        wc = rep.get_work_completed(tli)
        assert "01 Jan 2019" in wc
        assert "href" in wc

    @override_settings(TIME_ZONE="America/Toronto")
    def test_get_work_completed_plain(self):
        rep = reports.QCSummaryReport()
        rep.report_format = "csv"
        tz = pytz.timezone("America/Toronto")
        work_completed = tz.localize(timezone.datetime(2019, 1, 1, 12))
        tli = utils.create_test_list_instance(work_completed=work_completed)
        wc = rep.get_work_completed(tli)
        assert "01 Jan 2019" in wc
        assert "href" not in wc

    @override_settings(TIME_ZONE="America/Toronto")
    def test_get_pass_fail_html(self):
        rep = reports.QCSummaryReport()
        rep.report_format = "html"
        tli = utils.create_test_list_instance()
        pf = rep.get_pass_fail_status(tli)
        assert "<span" in pf

    @override_settings(TIME_ZONE="America/Toronto")
    def test_get_pass_fail_plain(self):
        rep = reports.QCSummaryReport()
        rep.report_format = "csv"
        tli = utils.create_test_list_instance()
        pf = rep.get_pass_fail_status(tli)
        assert pf == ''  # no test instances, just want to make sure no html tags in status for plain text report

    def test_get_tlis_for_site(self):
        site = USite.objects.create(name="site")
        unit = utils.create_unit(site=site)
        utc = utils.create_unit_test_collection(unit=unit)
        tli = utils.create_test_list_instance(unit_test_collection=utc)

        unit2 = utils.create_unit(site=None)
        utc2 = utils.create_unit_test_collection(unit=unit2)
        utils.create_test_list_instance(unit_test_collection=utc2)

        qs = TestListInstance.objects.all()
        tlis = reports.QCSummaryReport().get_tlis_for_site(qs, site)
        assert list([x.pk for x in tlis]) == [tli.pk]

    def test_get_tlis_for_null_site(self):
        site = USite.objects.create(name="site")
        unit = utils.create_unit(site=site)
        utc = utils.create_unit_test_collection(unit=unit)
        utils.create_test_list_instance(unit_test_collection=utc)

        unit2 = utils.create_unit(site=None)
        utc2 = utils.create_unit_test_collection(unit=unit2)
        tli2 = utils.create_test_list_instance(unit_test_collection=utc2)

        qs = TestListInstance.objects.all()
        tlis = reports.QCSummaryReport().get_tlis_for_site(qs, None)
        assert list([x.pk for x in tlis]) == [tli2.pk]

    def test_to_table(self):

        site = USite.objects.create(name="site")
        unit = utils.create_unit(site=site)
        utc = utils.create_unit_test_collection(unit=unit)
        utils.create_test_list_instance(unit_test_collection=utc)

        unit2 = utils.create_unit(site=None)
        utc2 = utils.create_unit_test_collection(unit=unit2)
        utils.create_test_list_instance(unit_test_collection=utc2)

        rep = reports.QCSummaryReport()
        rep.report_format = "csv"
        context = rep.get_context()
        table = rep.to_table(context)

        header_row = table.index([
            'Site',
            'Unit',
            'Test list',
            'Due Date',
            'Work Completed',
            'Pass/Fail Status',
            'Link',
        ])
        # should be two tlis after header
        assert len(table[header_row + 1:]) == 2


class TestReportInterface(BaseQATests):

    def setUp(self):
        super().setUp()
        self.login()
        self.open(reverse("reports"))
        self.wait.until(e_c.presence_of_element_located((By.ID, 'select2-id_root-report_type-container')))
        self.report_type_select = Select(self.driver.find_element_by_id('id_root-report_type'))

    def test_report_preview(self):
        """Select report and make sure it previews"""
        self.report_type_select.select_by_visible_text(reports.QCSummaryReport.name)
        self.wait.until(e_c.presence_of_element_located((By.ID, 'id_work_completed')))
        self.driver.find_element_by_id("preview").click()
        self.driver.find_element_by_css_selector('#report .container-fluid')

    def test_save_report(self):
        """Select report and make sure it previews"""
        self.report_type_select.select_by_visible_text(reports.QCSummaryReport.name)
        self.wait.until(e_c.presence_of_element_located((By.ID, 'id_work_completed')))
        assert models.SavedReport.objects.count() == 0
        self.driver.find_element_by_id("save").click()
        self.wait.until(e_c.presence_of_element_located((By.CLASS_NAME, 'success-message')))
        assert models.SavedReport.objects.count() == 1
        sr = models.SavedReport.objects.first()
        self.wait.until(e_c.presence_of_element_located((By.ID, 'report-id-%s' % sr.pk)))

    def test_load_report(self):
        """Select report from table and make sure it loads"""

        sr = models.SavedReport.objects.create(
            report_type=reports.QCSummaryReport.report_type,
            report_format="pdf",
            title="title",
            filters={'work_completed': ['2 Jan 1989', '4 Jan 1990']},
            created_by=self.user,
            modified_by=self.user,
        )
        # need to reload page to get report table
        self.driver.refresh()
        self.wait.until(e_c.presence_of_element_located((By.ID, 'report-id-%s' % sr.pk)))
        self.driver.find_element_by_id('report-id-%s' % sr.pk).click()
        wc = self.driver.find_element_by_id('id_work_completed')
        assert wc.get_attribute("value") == "02 Jan 1989 - 04 Jan 1990"

    def test_schedule_report(self):
        """Select report from table and make sure it loads"""

        sr = models.SavedReport.objects.create(
            report_type=reports.QCSummaryReport.report_type,
            report_format="pdf",
            title="title",
            filters={'work_completed': ['2 Jan 1989', '4 Jan 1990']},
            created_by=self.user,
            modified_by=self.user,
        )
        # need to reload page to get report table
        self.driver.refresh()
        self.wait.until(e_c.presence_of_element_located((By.ID, 'report-id-%s' % sr.pk)))
        self.driver.find_element_by_id('report-id-%s' % sr.pk).click()

        self.driver.find_element_by_id("report-id-%s-schedule" % sr.pk).click()

        time.sleep(0.2)
        select = Select(self.driver.find_element_by_id('id_schedule-time'))
        select.select_by_index(1)
        self.driver.find_element_by_id("id_schedule-emails").send_keys("a@b.com")

        self.wait.until(e_c.presence_of_element_located((By.CLASS_NAME, 'add-date')))
        self.driver.find_element_by_class_name("add-date").click()

        self.driver.find_element_by_id("schedule").click()

        self.wait.until(e_c.presence_of_element_located((By.CLASS_NAME, 'alert-success')))
        assert timezone.localtime(timezone.now()
                                  ).strftime("%Y%m%d") in str(models.ReportSchedule.objects.first().schedule)

    def test_clear_schedule(self):
        """Select report from table and make sure it loads"""

        sr = models.SavedReport.objects.create(
            report_type=reports.QCSummaryReport.report_type,
            report_format="pdf",
            title="title",
            filters={'work_completed': ['2 Jan 1989', '4 Jan 1990']},
            created_by=self.user,
            modified_by=self.user,
        )
        rec = "RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE"
        models.ReportSchedule.objects.create(
            report=sr,
            time="00:00:00",
            schedule=rec,
            created_by=self.user,
            modified_by=self.user,
        )

        # need to reload page to get report table
        self.driver.refresh()
        self.wait.until(e_c.presence_of_element_located((By.ID, 'report-id-%s' % sr.pk)))

        self.driver.find_element_by_id("report-id-%s-schedule" % sr.pk).click()

        self.wait.until(e_c.visibility_of_all_elements_located((By.ID, 'clear-schedule')))
        self.driver.find_element_by_id("clear-schedule").click()
        self.wait.until(e_c.presence_of_element_located((By.CLASS_NAME, 'alert-success')))
        assert models.ReportSchedule.objects.count() == 0


class TestSavedReportAdmin:

    def test_has_add_perm(self):
        site = AdminSite()
        adm = admin.SavedReportAdmin(models.SavedReport, site)
        assert not adm.has_add_permission(None)

    def test_report_schedule_form(self):
        form = admin.ReportScheduleForm()
        form.cleaned_data = {}
        form.clean()
        assert "You must select" in form.errors['__all__'][0]


class TestReportScheduleAdmin(TestCase):

    def setUp(self):
        site = AdminSite()
        self.admin = admin.ReportScheduleAdmin(models.ReportSchedule, site)
        r = models.SavedReport(report_type=reports.QCSummaryReport.report_type, report_format="pdf", title="title")
        self.rs = models.ReportSchedule(report=r)

    def test_get_report_type(self):
        assert self.admin.get_report_type(self.rs) == reports.QCSummaryReport.name

    def test_get_report_format(self):
        assert self.admin.get_report_format(self.rs) == "PDF"

    def test_get_report_title(self):
        assert self.admin.get_report_title(self.rs) == "title"


class TestReportModels(TestCase):

    def setUp(self):

        self.user = User.objects.create_superuser("user", "a@b.com", "password")
        self.report = models.SavedReport.objects.create(
            report_type=reports.QCSummaryReport.report_type,
            report_format="pdf",
            title="title",
            filters={'work_completed': ['2 Jan 1989', '4 Jan 1990']},
            created_by=self.user,
            modified_by=self.user,
        )

    def test_savedreport_str(self):
        assert str(self.report) == "#%d. title - QC Summary - PDF" % self.report.pk


class TestReportTasks(TestCase):

    def setUp(self):

        self.user = User.objects.create_superuser("user", "a@b.com", "password")
        self.report = models.SavedReport.objects.create(
            report_type=reports.QCSummaryReport.report_type,
            report_format="pdf",
            title="title",
            filters={'work_completed': ['2 Jan 1989', '4 Jan 1990']},
            created_by=self.user,
            modified_by=self.user,
        )
        self.schedule = models.ReportSchedule.objects.create(
            pk=123,
            report=self.report,
            time="00:00",
            schedule="RRULE:FREQ=DAILY",
            created_by=self.user,
            modified_by=self.user,
        )
        self.schedule.emails = "a@b.com"
        self.schedule.save()

        # delete preconfigured schedules to make counting easier
        Schedule.objects.all().delete()

    def test_send_report(self):
        now = timezone.now()
        tasks.send_report(self.schedule.pk)
        self.schedule.refresh_from_db()
        assert self.schedule.last_sent >= now
        assert "QATrack+ Reports:" in mail.outbox[0].subject

    def test_send_report_non_existent(self):
        tasks.send_report(self.schedule.pk + 1)
        self.schedule.refresh_from_db()
        assert self.schedule.last_sent is None
        assert len(mail.outbox) == 0

    def test_send_report_no_recipients(self):
        self.schedule.emails = ""
        self.schedule.save()
        tasks.send_report(self.schedule.pk)
        self.schedule.refresh_from_db()
        assert self.schedule.last_sent is None
        assert len(mail.outbox) == 0

    def test_schedule_report(self):
        next_run = timezone.now() + timezone.timedelta(hours=1)
        tasks.schedule_report(self.schedule, next_run)
        assert Schedule.objects.count() == 1

    def test_run_reports(self):
        """schedule report to run 5 minutes from now then run run_reports. Report should be scheduled then"""
        now = timezone.localtime(timezone.now())
        self.schedule.time = (now + timezone.timedelta(minutes=5)).strftime("%H:%M")
        self.schedule.save()
        assert Schedule.objects.count() == 0
        tasks.run_reports()
        assert Schedule.objects.count() == 1

    def test_run_reports_later(self):
        """schedule report to run 25 minutes from now then run run_reports. Report should not be scheduled"""
        now = timezone.localtime(timezone.now())
        self.schedule.time = (now + timezone.timedelta(minutes=25)).strftime("%H:%M")
        self.schedule.save()
        assert Schedule.objects.count() == 0
        tasks.run_reports()
        assert Schedule.objects.count() == 0