import re

from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import Group, User
from django.contrib.contenttypes.fields import (
    GenericForeignKey,
    GenericRelation,
)
from django.contrib.contenttypes.models import ContentType
from django.core import urlresolvers
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.translation import ugettext as _
from django_comments.models import Comment

from qatrack.qa import utils
from qatrack.qa.testpack import TestPackMixin
from qatrack.units.models import Unit

# All available test types
BOOLEAN = "boolean"
NUMERICAL = "numerical"
SIMPLE = "simple"
CONSTANT = "constant"
COMPOSITE = "composite"
MULTIPLE_CHOICE = "multchoice"
STRING = "string"
UPLOAD = "upload"
STRING_COMPOSITE = "scomposite"

NUMERICAL_TYPES = (COMPOSITE, CONSTANT, SIMPLE, )
STRING_TYPES = (STRING, STRING_COMPOSITE, MULTIPLE_CHOICE, )
COMPOSITE_TYPES = (COMPOSITE, STRING_COMPOSITE,)
CALCULATED_TYPES = (UPLOAD, COMPOSITE, STRING_COMPOSITE, )
NO_SKIP_REQUIRED_TYPES = (COMPOSITE, CONSTANT, STRING_COMPOSITE, )

TEST_TYPE_CHOICES = (
    (BOOLEAN, "Boolean"),
    (SIMPLE, "Simple Numerical"),
    (MULTIPLE_CHOICE, "Multiple Choice"),
    (CONSTANT, "Constant"),
    (COMPOSITE, "Composite"),
    (STRING, "String"),
    (STRING_COMPOSITE, "String Composite"),
    (UPLOAD, "File Upload"),
)
MAX_STRING_VAL_LEN = 1024

# tolerance types
ABSOLUTE = "absolute"
PERCENT = "percent"

TOL_TYPE_CHOICES = (
    (ABSOLUTE, "Absolute"),
    (PERCENT, "Percentage"),
    (MULTIPLE_CHOICE, "Multiple Choice"),
)

# reference types
REF_TYPE_CHOICES = (
    (NUMERICAL, "Numerical"),
    (BOOLEAN, "Yes / No"),
)


# pass fail choices
NOT_DONE = "not_done"
OK = "ok"
TOLERANCE = "tolerance"
ACTION = "action"
NO_TOL = "no_tol"

ACT_HIGH = "act_high"
ACT_LOW = "act_low"
TOL_HIGH = "tol_high"
TOL_LOW = "tol_low"

status_displays = settings.TEST_STATUS_DISPLAY
NOT_DONE_DISP = status_displays.get("not_done", "Not Done")
OK_DISP = status_displays.get("ok", "OK")
TOL_DISP = status_displays.get("tolerance", "Tolerance")
ACT_DISP = status_displays.get("action", "Action")
NO_TOL_DISP = status_displays.get("no_tol", "No Tol Set")

PASS_FAIL_CHOICES = (
    (NOT_DONE, NOT_DONE_DISP),
    (OK, OK_DISP),
    (TOLERANCE, TOL_DISP),
    (ACTION, ACT_DISP),
    (NO_TOL, NO_TOL_DISP),
)
PASS_FAIL_CHOICES_DISPLAY = dict(PASS_FAIL_CHOICES)

AUTO_REVIEW_DEFAULT = getattr(settings, "AUTO_REVIEW_DEFAULT", False)


# due date choices
NO_DUE_DATE = NO_TOL
NOT_DUE = OK
DUE = TOLERANCE
OVERDUE = ACTION
NEWLIST = NOT_DONE

EPSILON = 1E-10

re_255 = '([0-9]|[1-9][0-9]|1[0-9][0-9]|2[0-4][0-9]|25[0-5])'
color_re = re.compile('^rgba\(' + re_255 + ',' + re_255 + ',' + re_255 + ',(0(\.[0-9][0-9]?)?|1)\)$')
validate_color = RegexValidator(color_re, _('Enter a valid color.'), 'invalid')

#  A collection of the permissions most relevant to QATrack+
PERMISSIONS = (
    (
        'Performing',
        (
            (
                'qa.add_testlistinstance',
                'Can add test list instance',
                'Allow user to perform test lists and continue in-progress lists',
            ),
            (
                'qa.can_choose_frequency',
                'Choose QA by frequency',
                'Allows user to pre-emptively filter test lists based on frequency.',
            ),
            (
                'qa.can_view_ref_tol',
                'Can view refs and tols',
                'Makes reference and tolerance values visible when performing a test list.',
            ),
            (
                'qa.can_view_history',
                'Can view test history',
                'Makes test history visible when performing a test list.',
            ),
            (
                'qa.can_skip_without_comment',
                'Can skip without comment',
                'Allow a user to skip tests with adding a comment',
            ),
            (
                'qa.can_override_date',
                'Can override date',
                'Allow a user to override the work_completed data',
            ),
            (
                'qa.can_perform_subset',
                'Can perform subset of tests',
                'Allow a user to filter tests to perform  based on a tests category',
            ),
            (
                'qa.change_testlistinstance',
                'Can edit prior test results',
                'Allow a user to edit already completed test results',
            ),
            (
                'qa.can_save_in_progress',
                'Can save test lists in progress',
                'Can save test lists with the "In Progress" flag set',
            ),
        ),
    ),
    (
        'Reviewing',
        (
            (
                'qa.can_view_completed',
                'Can view previously completed instances',
                'Allow a user to view previous test list results',
            ),
            (
                'qa.can_view_overview',
                'Can view program overview',
                'Allows a user to view the overall program status',
            ),
            (
                'qa.can_review',
                'Can review tests',
                'Allows a user to perform review & approval functions',
            ),
            (
                'qa.can_view_charts',
                'Can chart test history',
                'Gives user the ability to view and create charts of historical test results',
            ),
            (
                'qa.can_review_own_tests',
                'Can review self-performed tests',
                'Allows a user to perform review & approval functions on self-performed tests',
            ),
            (
                'qa.can_review_non_visible_tli',
                'Can review non visible test list instances',
                'Allows a user to review test list instances that are not visible to any of their groups',
            )
        ),
    ),
)

if settings.USE_SERVICE_LOG:
    PERMISSIONS += (
        (
            'Service Log',
            (
                (
                    'service_log.perform_returntoserviceqa',
                    'Can perform return to service qa',
                    'Allow user to perform qa linked to service events.',
                ),
                (
                    'service_log.view_returntoserviceqa',
                    'Can view existing return to service qa',
                    'Allow user to view qa linked to service events.',
                ),
                (
                    'service_log.add_serviceevent',
                    'Can create service event',
                    'Allows user to create new service events.',
                ),
                (
                    'service_log.view_serviceevent',
                    'Can view service events',
                    'Allows user to view existing service events.',
                ),
                (
                    'service_log.review_serviceevent',
                    'Can review service events',
                    'Allows user to change status of service events to statuses with \'is review required = false\'.',
                ),
                (
                    'parts.add_part',
                    'Can add part',
                    'Allow user to enter new parts.',
                ),
                (
                    'parts.view_part',
                    'Can view parts',
                    'Allow user to view existing parts',
                ),
            )
        ),
    )


class FrequencyManager(models.Manager):
    """Provides a convenience method for grabbing available convenience slug/names"""

    def frequency_choices(self):
        return self.get_queryset().values_list("slug", "name")

    def get_by_natural_key(self, slug):
        return self.get(slug=slug)


class Frequency(models.Model):
    """Frequencies for performing QA tasks with configurable due dates"""

    name = models.CharField(max_length=50, unique=True, help_text=_("Display name for this frequency"))

    slug = models.SlugField(
        max_length=50, unique=True,
        help_text=_("Unique identifier made of lowercase characters and underscores for this frequency")
    )

    nominal_interval = models.PositiveIntegerField(help_text=_("Nominal number of days between test completions"))
    due_interval = models.PositiveIntegerField(
        help_text=_("How many days since last completed until a test with this frequency is shown as due")
    )
    overdue_interval = models.PositiveIntegerField(
        help_text=_("How many days since last completed until a test with this frequency is shown as over due")
    )

    objects = FrequencyManager()

    class Meta:
        verbose_name_plural = "frequencies"
        ordering = ("nominal_interval",)
        permissions = (
            ("can_choose_frequency", "Choose QA by Frequency"),
        )

    def nominal_delta(self):
        """return datetime delta for nominal interval"""
        if self.nominal_interval is not None:
            return timezone.timedelta(days=self.nominal_interval)

    def due_delta(self):
        """return datetime delta for nominal interval"""
        if self.due_interval is not None:
            return timezone.timedelta(days=self.due_interval)

    def natural_key(self):
        return (self.slug,)

    def __str__(self):
        return self.name


class StatusManager(models.Manager):
    """manager for TestInstanceStatus"""

    def default(self):
        """return the default TestInstanceStatus"""
        try:
            return self.get_queryset().get(is_default=True)
        except TestInstanceStatus.DoesNotExist:
            return

    def get_by_natural_key(self, slug):
        return self.get(slug=slug)


class TestInstanceStatus(models.Model):
    """Configurable statuses for QA Tests"""

    name = models.CharField(max_length=50, help_text=_("Display name for this status type"), unique=True)
    slug = models.SlugField(
        max_length=50, unique=True,
        help_text=_("Unique identifier made of lowercase characters and underscores for this status")
    )

    description = models.TextField(
        help_text=_("Give a brief description of what type of test results should be given this status"),
        null=True, blank=True
    )

    is_default = models.BooleanField(
        default=False,
        help_text=_("Check to make this status the default for new Test Instances")
    )

    requires_review = models.BooleanField(
        default=True,
        help_text=_("Check to indicate that Test Instances with this status require further review"),
    )

    export_by_default = models.BooleanField(
        default=True,
        help_text=_(
            "Check to indicate whether tests with this status should be exported by "
            "default (e.g. for graphing/control charts)"
        ),
    )

    valid = models.BooleanField(
        default=True,
        help_text=_(
            "If unchecked, data with this status will not be exported and "
            "the TestInstance will not be considered a valid completed Test"
        )
    )

    colour = models.CharField(default=settings.DEFAULT_TEST_STATUS_COLOUR, max_length=22, validators=[validate_color])

    objects = StatusManager()

    class Meta:
        verbose_name_plural = "statuses"

    def save(self, *args, **kwargs):
        """set status to unreviewed if not previously set"""

        cur_default = TestInstanceStatus.objects.default()
        if cur_default is None:
            self.is_default = True
        elif self.is_default:
            cur_default.is_default = False
            cur_default.save()

        super(TestInstanceStatus, self).save(*args, **kwargs)

    def natural_key(self):
        return (self.slug,)

    def __str__(self):
        return self.name


class AutoReviewRule(models.Model):

    pass_fail = models.CharField(
        help_text="Pass fail state of test instances to apply this rule to.",
        max_length=15,
        choices=PASS_FAIL_CHOICES,
        unique=True,
    )
    status = models.ForeignKey(
        TestInstanceStatus,
        help_text="Status to assign test instance based on its pass/fail state",
    )

    def __str__(self):
        return "%s => %s" % (PASS_FAIL_CHOICES_DISPLAY[self.pass_fail], self.status)


class Reference(models.Model):
    """Reference values for various QA :model:`Test`s"""

    name = models.CharField(max_length=255, help_text=_("Enter a short name for this reference"))
    type = models.CharField(max_length=15, choices=REF_TYPE_CHOICES, default=NUMERICAL)
    value = models.FloatField(help_text=_("Enter the reference value for this test."))

    # who created this reference
    created = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, editable=False, related_name="reference_creators")

    # who last modified this reference
    modified = models.DateTimeField(auto_now=True)
    modified_by = models.ForeignKey(User, editable=False, related_name="reference_modifiers")

    class Meta:
        default_permissions = ()

    def clean_fields(self):
        if self.type == BOOLEAN and self.value not in (0, 1):
            raise ValidationError({"value": ["Boolean values must be 0 or 1"]})

    def value_display(self):
        """return user friendly display value for this reference"""

        if self.value is None:
            return ""
        if self.type == BOOLEAN:
            return "Yes" if int(self.value) == 1 else "No"
        return "%.6G" % (self.value)

    def __str__(self):
        """more helpful display name"""
        return self.value_display()


class ToleranceManager(models.Manager):

    def get_by_natural_key(self, name):
        return self.get(name=name)


class Tolerance(models.Model):
    """
    Model for storing tolerance/action levels and tolerance/action choices
    for multiple choice type tests
    """

    name = models.CharField(max_length=255, unique=True, editable=False)

    type = models.CharField(
        max_length=20,
        help_text=_("Select whether this will be an absolute or relative tolerance criteria"),
        choices=TOL_TYPE_CHOICES,
    )
    act_low = models.FloatField(
        verbose_name=_("%s Low" % ACT_DISP),
        help_text=_("Value of lower %s level" % ACT_DISP),
        null=True,
        blank=True,
    )
    tol_low = models.FloatField(
        verbose_name=_("%s Low" % TOL_DISP),
        help_text=_("Value of lower %s level" % TOL_DISP),
        null=True,
        blank=True,
    )
    tol_high = models.FloatField(
        verbose_name=_("%s High" % TOL_DISP),
        help_text=_("Value of upper %s level" % TOL_DISP),
        null=True,
        blank=True,
    )
    act_high = models.FloatField(
        verbose_name=_("%s High" % ACT_DISP),
        help_text=_("Value of upper %s level" % ACT_DISP),
        null=True,
        blank=True,
    )

    mc_pass_choices = models.CharField(
        verbose_name=_("Multiple Choice %s Values" % OK_DISP),
        max_length=2048,
        help_text=_("Comma seperated list of choices that are considered passing"),
        null=True,
        blank=True,
    )

    mc_tol_choices = models.CharField(
        verbose_name=_("Multiple Choice %s Values" % TOL_DISP),
        max_length=2048,
        help_text=_("Comma seperated list of choices that are considered at tolerance"),
        null=True,
        blank=True,
    )

    bool_warning_only = models.BooleanField(
        verbose_name=_("Boolean Warning Only"),
        help_text=_("Boolean tests not matching references should be considered at tolerance rather than action"),
        default=False,
    )

    # who created this tolerance
    created_date = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, editable=False, related_name="tolerance_creators")

    # who last modified this tolerance
    modified_date = models.DateTimeField(auto_now=True)
    modified_by = models.ForeignKey(User, editable=False, related_name="tolerance_modifiers")

    objects = ToleranceManager()

    class Meta:

        ordering = ["type", "act_low", "tol_low", "tol_high", "act_high"]

    def pass_choices(self):
        return self.mc_pass_choices.split(",") if self.mc_pass_choices else []

    def tol_choices(self):
        return self.mc_tol_choices.split(",") if self.mc_tol_choices else []

    def clean_choices(self):
        """make sure choices provided if Tolerance Type is MultipleChoice"""

        errors = []

        if self.type == MULTIPLE_CHOICE:

            if (None, None, None, None) != (self.act_low, self.tol_low, self.tol_high, self.act_high):
                errors.append("Value set for tolerance or action but type is Multiple Choice")

            if self.mc_pass_choices is None or self.mc_pass_choices.strip() == "":
                errors.append("You must give at least l passing choice for a multiple choice tolerance")
            else:

                pass_choices = [x.strip() for x in self.mc_pass_choices.split(",") if x.strip()]
                self.mc_pass_choices = ",".join(pass_choices)

                if self.mc_tol_choices:
                    tol_choices = [x.strip() for x in self.mc_tol_choices.split(",") if x.strip()]
                else:
                    tol_choices = []

                if tol_choices:
                    self.mc_tol_choices = ",".join(tol_choices)

        elif self.type != MULTIPLE_CHOICE:
            if (self.mc_pass_choices or self.mc_tol_choices):
                errors.append("Value set for pass choices or tolerance choices but type is not Multiple Choice")

        if errors:
            raise ValidationError({"mc_pass_choices": errors})

    def clean_tols(self):
        if self.type in (ABSOLUTE, PERCENT):
            if all([getattr(self, c) is None for c in (ACT_HIGH, ACT_LOW, TOL_HIGH, TOL_LOW,)]):
                raise ValidationError({
                    ACT_LOW: [
                        "You must set at least one %s or %s level for this tolerance type" % (TOL_DISP, ACT_DISP)
                    ]
                })

    def clean_fields(self, exclude=None):
        """extra validation for Tests"""
        super(Tolerance, self).clean_fields(exclude)
        self.clean_choices()
        self.clean_tols()

    def tolerances_for_value(self, value):
        """return dict containing tolerances for input value"""

        tols = {ACT_HIGH: None, ACT_LOW: None, TOL_LOW: None, TOL_HIGH: None}
        attrs = list(tols.keys())

        if value is None:
            return tols
        elif self.type == ABSOLUTE:
            for attr in attrs:
                tv = getattr(self, attr)
                tols[attr] = value + tv if tv is not None else None
        elif self.type == PERCENT:
            for attr in attrs:
                tv = getattr(self, attr)
                tols[attr] = value * (1. + tv / 100.) if tv is not None else None
        return tols

    def save(self, *args, **kwargs):
        self.name = get_tolerance_name(self)
        super(Tolerance, self).save(*args, **kwargs)

    def natural_key(self):
        return (self.name,)

    def __str__(self):
        """more helpful interactive display name"""
        return self.name


def get_tolerance_name(tol):
    """Note use an external function here rather than Tolerance method since we also use it
    in a migration where model methods can't be called"""

    vals = (tol.act_low, tol.tol_low, tol.tol_high, tol.act_high)
    if tol.type == ABSOLUTE:
        vals = ["%.3f" % v if v is not None else '--' for v in vals]
        return "Absolute(%s, %s, %s, %s)" % tuple(vals)
    elif tol.type == PERCENT:
        vals = ["%.2f%%" % v if v is not None else '--' for v in vals]
        return "Percent(%s, %s, %s, %s)" % tuple(vals)
    elif tol.type == MULTIPLE_CHOICE:
        return "M.C.(%s=%s, %s=%s)" % (OK_DISP, ":".join(tol.pass_choices()), TOL_DISP, ":".join(tol.tol_choices()))
    elif tol.type == BOOLEAN:
        act = settings.TEST_STATUS_DISPLAY["action"]
        tol_ = settings.TEST_STATUS_DISPLAY["tolerance"]
        return "Boolean(%s on fail)" % (tol_ if tol.bool_warning_only else act)


class CategoryManager(models.Manager):
    def get_by_natural_key(self, name):
        return self.get(name=name)


class Category(models.Model):
    """A model used for categorizing :model:`Test`s"""

    NK_FIELDS = ['name']

    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(
        max_length=255, unique=True,
        help_text=_("Unique identifier made of lowercase characters and underscores")
    )
    description = models.TextField(
        help_text=_("Give a brief description of what type of tests should be included in this grouping")
    )

    objects = CategoryManager()

    class Meta:
        verbose_name_plural = "categories"
        ordering = ("name",)

    @classmethod
    def get_testpack_fields(cls):
        exclude = ["id"]
        return [f.name for f in cls._meta.concrete_fields if f.name not in exclude]

    def natural_key(self):
        return (self.name,)

    def __str__(self):
        """return display representation of object"""
        return self.name


class TestManager(models.Manager):

    def get_by_natural_key(self, name):
        return self.get(name=name)


class Test(models.Model, TestPackMixin):
    """Test to be completed as part of a QA :model:`TestList`"""

    NK_FIELDS = ['name']

    VARIABLE_RE = re.compile("^[a-zA-Z_]+[0-9a-zA-Z_]*$")
    RESULT_RE = re.compile("^\s*result\s*=.*$", re.MULTILINE)

    name = models.CharField(max_length=255, help_text=_("Name for this test"), db_index=True, unique=True)
    slug = models.SlugField(
        verbose_name="Macro name", max_length=128,
        help_text=_(
            "A short variable name consisting of alphanumeric characters and "
            "underscores for this test (to be used in composite calculations). "
        ),
        db_index=True,
    )
    description = models.TextField(
        help_text=_("A concise description of what this test is for (optional. You may use HTML markup)"),
        blank=True,
        null=True
    )
    procedure = models.CharField(
        max_length=512,
        help_text=_("Link to document describing how to perform this test"),
        blank=True,
        null=True,
    )
    category = models.ForeignKey(Category, help_text=_("Choose a category for this test"))
    chart_visibility = models.BooleanField("Test item visible in charts?", default=True)
    auto_review = models.BooleanField(_("Allow auto review of this test?"), default=AUTO_REVIEW_DEFAULT)

    type = models.CharField(
        max_length=10, choices=TEST_TYPE_CHOICES, default=SIMPLE,
        help_text=_("Indicate if this test is a %s" % (','.join(x[1].title() for x in TEST_TYPE_CHOICES)))
    )

    hidden = models.BooleanField(_("Hidden"), help_text=_("Don't display this test when performing QA"), default=False)
    skip_without_comment = models.BooleanField(
        _("Skip without comment"),
        help_text=_("Allow users to skip this test without a comment"),
        default=False,
    )
    display_image = models.BooleanField(
        "Display image",
        help_text=_("Image uploads only: Show uploaded images under the testlist"),
        default=False,
    )
    choices = models.CharField(
        max_length=2048,
        help_text=_("Comma seperated list of choices for multiple choice test types"),
        null=True,
        blank=True,
    )
    constant_value = models.FloatField(help_text=_("Only required for constant value types"), null=True, blank=True)

    calculation_procedure = models.TextField(null=True, blank=True, help_text=_(
        "For Composite Tests Only: Enter a Python snippet for evaluation of this test."
    ))

    # for keeping a very basic history
    created = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, editable=False, related_name="test_creator")
    modified = models.DateTimeField(auto_now=True)
    modified_by = models.ForeignKey(User, editable=False, related_name="test_modifier")

    objects = TestManager()

    def is_numerical_type(self):
        """return whether or not this is a numerical test"""
        return self.type in NUMERICAL_TYPES

    def is_string_type(self):
        return self.type in STRING_TYPES

    def is_string(self):
        return self.type == STRING

    def is_string_composite(self):
        return self.type == STRING_COMPOSITE

    def can_attach(self):
        return self.type in (STRING_COMPOSITE, COMPOSITE, UPLOAD)

    def is_upload(self):
        """Return whether or not this is a boolean test"""
        return self.type == UPLOAD

    def is_boolean(self):
        """Return whether or not this is a boolean test"""
        return self.type == BOOLEAN

    def is_mult_choice(self):
        """return True if this is a multiple choice test else, false"""
        return self.type == MULTIPLE_CHOICE

    def skip_required(self):
        return self.type not in NO_SKIP_REQUIRED_TYPES

    def check_test_type(self, field, test_types, display):
        """check that correct test type is set"""
        if isinstance(test_types, str):
            test_types = [test_types]

        errors = []
        if field is not None and self.type not in test_types:
            errors.append(_("%s value provided, but Test Type is not %s" % (display, display)))

        if field is None and self.type in test_types:
            errors.append(_("Test Type is %s but no %s value provided" % (display, display)))
        return errors

    def clean_calculation_procedure(self):
        """make sure a valid calculation procedure"""

        if not self.calculation_procedure and self.type not in CALCULATED_TYPES:
            return

        errors = self.check_test_type(self.calculation_procedure, CALCULATED_TYPES, "Calculation Procedure")
        self.calculation_procedure = str(self.calculation_procedure).replace("\r\n", "\n")

        macro_var_set = re.findall("^\s*%s\s*=.*$" % (self.slug), self.calculation_procedure, re.MULTILINE)
        result_line = self.RESULT_RE.findall(self.calculation_procedure)
        if not (result_line or macro_var_set):
            if not self.calculation_procedure and self.is_upload():
                # don't require a user defined calc procedure for uploads
                self.calculation_procedure = "%s = None" % (self.slug, )
            else:
                errors.append(_(
                    'Snippet must set macro name to a value or contain a result line '
                    '(e.g. %s = my_var/another_var*2 or result = my_var/another_var*2)' % self.slug
                ))

        try:
            utils.tokenize_composite_calc(self.calculation_procedure)
        except utils.tokenize.TokenError:
            errors.append(_('Calculation procedure invalid: Possible cause is an unbalanced parenthesis'))

        if errors:
            raise ValidationError({"calculation_procedure": errors})

    def clean_constant_value(self):
        """make sure a constant value is provided if TestType is Constant"""
        errors = self.check_test_type(self.constant_value, CONSTANT, "Constant")
        if errors:
            raise ValidationError({"constant_value": errors})

    def clean_choices(self):
        """make sure choices provided if TestType is MultipleChoice"""
        errors = self.check_test_type(self.choices, MULTIPLE_CHOICE, "Multiple Choice")
        if self.type != MULTIPLE_CHOICE:
            return
        elif self.choices is None:
            errors.append("You must give at least 1 choice for a multiple choice test")
        else:
            choices = [x.strip() for x in self.choices.strip().split(",") if x.strip()]
            if len(choices) < 1:
                errors.append("You must give at least 1 choice for a multiple choice test")
            else:
                self.choices = ",".join(choices)
        if errors:
            raise ValidationError({"choices": errors})

    def clean_slug(self):
        """make sure slug is valid"""

        errors = []

        if not self.slug:
            errors.append(_("All tests require a macro name"))
        elif not self.VARIABLE_RE.match(self.slug):
            errors.append(_(
                "Macro names must contain only letters, numbers and underscores and start with a letter or underscore"
            ))

        if errors:
            raise ValidationError({"slug": errors})

    def clean_fields(self, exclude=None):
        """extra validation for Tests"""
        super(Test, self).clean_fields(exclude)
        self.clean_calculation_procedure()
        self.clean_constant_value()
        self.clean_slug()
        self.clean_choices()

    def get_choices(self):
        """return choices for multiple choice tests"""
        if self.type == MULTIPLE_CHOICE:
            cs = self.choices.split(",")
            return list(zip(cs, cs))

    @classmethod
    def get_testpack_fields(cls):
        exclude = ["id", "modified", "modified_by", "created", "created_by"]
        return [f.name for f in cls._meta.concrete_fields if f.name not in exclude]

    def get_testpack_dependencies(self):
        return [(Category, [self.category])]

    def natural_key(self):
        return (self.name,)
    natural_key.dependencies = ['qa.category']

    def __str__(self):
        """return display representation of object"""
        return "%s" % (self.name)


def get_utc_tlc_ids(active=None, units=None, frequencies=None):

    tlcct = ContentType.objects.get_for_model(TestListCycle)

    tlcs = UnitTestCollection.objects.filter(content_type=tlcct)

    if active is not None:
        tlcs = tlcs.filter(active=active)

    if units is not None:
        tlcs = tlcs.filter(unit__in=units)

    if frequencies is not None:
        tlcs = tlcs.filter(frequency__in=frequencies)

    tlcs = tlcs.values(
        'object_id'
    ).annotate(
        Count('object_id')
    ).filter(
        object_id__count__gt=0
    ).values_list("object_id", flat=True)

    return tlcs


def get_utc_tl_ids(active=None, units=None, frequencies=None):

    tlct = ContentType.objects.get_for_model(TestList)

    tls = UnitTestCollection.objects.filter(content_type=tlct)

    if active is not None:
        tls = tls.filter(active=active)

    if units is not None:
        tls = tls.filter(unit__in=units)

    if frequencies is not None:
        if None in frequencies:
            frequencies.remove(None)
            q = Q(frequency=None)
            if frequencies:
                q |= Q(frequency__in=frequencies)
        else:
            q = Q(frequency__in=frequencies)
        tls = tls.filter(q)

    tls = tls.values(
        'object_id'
    ).annotate(
        Count('object_id')
    ).filter(
        object_id__count__gt=0
    ).values_list("object_id", flat=True)

    tlcs = get_utc_tlc_ids(active=active, units=units, frequencies=frequencies)
    tls_from_tlcs = TestListCycleMembership.objects.filter(
        cycle_id__in=tlcs
    ).values_list("test_list_id", flat=True)

    return list(tls) + list(tls_from_tlcs)


class UnitTestInfoManager(models.Manager):

    # def get_queryset(self):
    #     return super(UnitTestInfoManager, self).get_queryset()

    def active(self, queryset=None):
        """Only return UTI's who's tests belong to at least 1 test list that
        is assigned to an active UnitTestCollection"""

        qs = queryset or self.get_queryset()

        tl_ids = get_utc_tl_ids(active=True)
        return qs.filter(
            Q(test__testlistmembership__test_list__in=tl_ids) |
            Q(test__testlistmembership__test_list__sublist__child__in=tl_ids)
        ).distinct()

    def inactive(self, queryset=None):
        """Only return UTI's who's tests don't belong to at least 1 test list that
        is assigned to an active UnitTestCollection"""

        qs = queryset or self.get_queryset()

        tl_ids = get_utc_tl_ids(active=True)
        return qs.exclude(
            Q(test__testlistmembership__test_list__in=tl_ids) |
            Q(test__testlistmembership__test_list__sublist__child__in=tl_ids)
        ).distinct()


class UnitTestInfo(models.Model):

    unit = models.ForeignKey(Unit)
    test = models.ForeignKey(Test)

    reference = models.ForeignKey(
        Reference,
        verbose_name=_("Current Reference"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    tolerance = models.ForeignKey(Tolerance, null=True, blank=True, on_delete=models.SET_NULL)

    active = models.BooleanField(help_text=_("Uncheck to disable this test on this unit"), default=True, db_index=True)

    assigned_to = models.ForeignKey(
        Group,
        help_text=_("QA group that this test list should nominally be performed by"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    objects = UnitTestInfoManager()

    class Meta:
        verbose_name_plural = "Set References & Tolerances"
        unique_together = ["test", "unit"]

        permissions = (
            ("can_view_ref_tol", "Can view Refs and Tols"),
        )

    def clean(self):
        """extra validation for Tests"""

        super(UnitTestInfo, self).clean()
        if None not in (self.reference, self.tolerance):
            if self.tolerance.type == PERCENT and self.reference.value == 0:
                msg = _("Percentage based tolerances can not be used with reference value of zero (0)")
                raise ValidationError(msg)

        if self.test.type == BOOLEAN:

            if self.reference is not None and self.reference.value not in (0., 1.):
                msg = _("Test type is BOOLEAN but reference value is not 0 or 1")
                raise ValidationError(msg)

    def get_history(self, number=5):
        """return last 'number' of instances for this test performed on input unit
        list is ordered in ascending dates
        """
        # hist = TestInstance.objects.filter(unit_test_info=self)
        hist = self.testinstance_set.select_related("status").all().order_by("-work_completed", "-pk")
        # hist = hist.select_related("status")
        return [(x.work_completed, x.value, x.pass_fail, x.status) for x in reversed(hist[:number])]

    def __str__(self):
        return "UnitTestInfo(%s)" % self.pk


class UnitTestInfoChange(models.Model):

    unit_test_info = models.ForeignKey(UnitTestInfo)
    reference = models.ForeignKey(
        Reference,
        verbose_name=_("Old Reference"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    reference_changed = models.BooleanField()
    tolerance = models.ForeignKey(
        Tolerance,
        verbose_name=_("Old Tolerance"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    tolerance_changed = models.BooleanField()
    comment = models.TextField(help_text=_("Reason for the change"))
    changed = models.DateTimeField(auto_now_add=True)
    changed_by = models.ForeignKey(User, editable=False)


class TestListMembershipManager(models.Manager):

    def get_by_natural_key(self, test_list_slug, test_name):
        return self.get(test_list__slug=test_list_slug, test__name=test_name)


class TestListMembership(models.Model):
    """Keep track of ordering for tests within a test list"""

    NK_FIELDS = ['test_list', 'test']

    test_list = models.ForeignKey("TestList")
    test = models.ForeignKey(Test)
    order = models.IntegerField(db_index=True)

    objects = TestListMembershipManager()

    class Meta:
        ordering = ("order",)
        unique_together = ("test_list", "test",)
        default_permissions = ()

    @classmethod
    def get_testpack_fields(cls):
        exclude = ["id"]
        return [f.name for f in cls._meta.concrete_fields if f.name not in exclude]

    def natural_key(self):
        return self.test_list.natural_key() + self.test.natural_key()
    natural_key.dependencies = ["qa.testlist", "qa.test"]

    def __str__(self):
        return "TestListMembership(pk=%s)" % self.pk


class TestCollectionInterface(models.Model):
    """abstract base class for Tests collection (i.e. TestList's and TestListCycles"""

    name = models.CharField(max_length=255, db_index=True)
    slug = models.SlugField(
        max_length=255,
        unique=True,
        help_text=_("A short unique name for use in the URL of this list"),
        db_index=True,
    )
    description = models.TextField(
        help_text=_("A concise description of this test checklist. (You may use HTML markup)"),
        null=True,
        blank=True,
    )
    javascript = models.TextField(
        help_text=_('Any extra javascript to run when loading perform page'),
        null=True,
        blank=True,
    )

    assigned_to = GenericRelation(
        "UnitTestCollection",
        content_type_field="content_type",
        object_id_field="object_id",
    )

    # for keeping a very basic history
    created = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, related_name="%(app_label)s_%(class)s_created", editable=False)
    modified = models.DateTimeField(auto_now=True)
    modified_by = models.ForeignKey(User, related_name="%(app_label)s_%(class)s_modified", editable=False)

    class Meta:
        abstract = True

    def get_list(self, day=0):
        return 0, self

    def next_list(self, day):
        """Return the day and list following the input day"""
        return 0, self

    def first(self):
        return self

    def all_tests(self):
        """returns all tests from this list and sublists"""
        return Test.objects.filter(
            testlistmembership__test_list__in=self.all_lists()
        ).distinct().prefetch_related("category")

    def test_list_members(self):
        """return all days from this collection"""
        raise NotImplementedError

    def content_type(self):
        """return content type of this object"""
        return ContentType.objects.get_for_model(self)


class TestListManager(models.Manager):

    def get_by_natural_key(self, slug):
        return self.get(slug=slug)


class TestList(TestCollectionInterface, TestPackMixin):
    """Container for a collection of QA :model:`Test`s"""

    NK_FIELDS = ['slug']

    tests = models.ManyToManyField(
        "Test",
        help_text=_("Which tests does this list contain"),
        through=TestListMembership,
    )

    warning_message = models.CharField(
        max_length=255, help_text=_("Message given when a test value is out of tolerance"),
        default=settings.DEFAULT_WARNING_MESSAGE
    )
    utcs = GenericRelation('UnitTestCollection', related_query_name='test_list')

    objects = TestListManager()

    def test_list_members(self):
        """return all days from this collection"""
        return TestList.objects.filter(pk=self.pk)

    def all_lists(self):
        """return query for self and all sublists"""
        children = TestList.objects.filter(pk__in=self.children.values_list("child__pk", flat=True))
        return TestList.objects.filter(pk=self.pk) | children

    def get_children(self):
        if not hasattr(self, "_children"):
            self._children = list(self.children.select_related("child").prefetch_related("child__tests"))
        return self._children

    def ordered_tests(self):
        """return list of all tests/sublist tests in order"""
        if not hasattr(self, "_ordered_tests"):
            tlms = self.testlistmembership_set.select_related(
                "test",
                "test__category"
            )
            tests = []
            for tlm in tlms:
                tests.append((tlm.order, tlm.order, tlm.test))

            for sublist in self.get_children():
                order = sublist.order
                ordered_tests = sublist.child.ordered_tests()
                for i, test in enumerate(ordered_tests):
                    tests.append((order, i, test))

            self._ordered_tests = [x[-1] for x in sorted(tests, key=lambda y: y[:-1])]
        return self._ordered_tests

    def ordered_members(self):
        """Return list of tests and sublists sorted according to their order"""
        members = {}
        for sublist in self.get_children():
            members[sublist.order] = sublist.child
        for tlm in self.testlistmembership_set.all():
            members[tlm.order] = tlm.test

        return [t[1] for t in sorted(members.items())]

    def sublist_borders(self, tests=None):
        """Return indexes where visible marks should be shown for sublists
        with visibility enabled"""

        if tests is None:
            tests = self.ordered_tests()

        n_total_tests = len(tests)
        borders = {
            'starts': {
                0: {'class': 'first'},
            },
            'ends': {
                (n_total_tests - 1): "__end__"
            },
        }
        test_sub = {}
        sub_test_count = {}
        for sublist in self.get_children():
            if not sublist.outline:
                continue
            stests = sublist.child.ordered_tests()
            sub_test_count[sublist.pk] = len(stests)
            for t in stests:
                test_sub[t.pk] = sublist

        processed_subs = set()
        for i, test in enumerate(tests):
            if test.pk in test_sub:
                sublist = test_sub[test.pk]
                if sublist.pk not in processed_subs:
                    processed_subs.add(sublist.pk)
                    borders['starts'][i] = {
                        'class': 'sublist',
                        'name': sublist.child.name,
                        'description': sublist.child.description,
                    }
                    ntests = sub_test_count[sublist.pk]
                    borders['ends'][i + ntests - 1] = True

        return borders

    @classmethod
    def get_testpack_fields(cls):
        exclude = ["id", "created", "created_by", "modified", "modified_by"]
        return [f.name for f in cls._meta.concrete_fields if f.name not in exclude]

    def get_testpack_dependencies(self):
        sublists = list(Sublist.objects.filter(parent=self).select_related("child"))
        all_tests = list(self.all_tests())
        tlms = self.testlistmembership_set.all()
        for sl in sublists:
            tlms |= sl.child.testlistmembership_set.all()

        return [
            (Category,
             [s.category for s in all_tests]),
            (Test, all_tests),
            (TestListMembership, tlms),
            (TestList,
             [sl.child for sl in sublists]),
            (Sublist, sublists),
        ]

    def natural_key(self):
        return (self.slug,)

    def __len__(self):
        return 1

    def __str__(self):
        """return display representation of object"""
        return "(%s) %s" % (self.pk, self.name)

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        super(TestList, self).save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )
        self.utcs.update(name=self.name)


class Sublist(models.Model):

    NK_FIELDS = ['parent', 'child']

    parent = models.ForeignKey(TestList, related_name="children")
    child = models.ForeignKey(TestList)
    outline = models.BooleanField(
        default=False,
        help_text=(
            "Check to indicate whether sublist tests should be distinguished visually from parent tests"
        ),
    )

    order = models.IntegerField(db_index=True)

    class Meta:
        ordering = ("order",)
        unique_together = ("parent", "child",)

    @classmethod
    def get_testpack_fields(cls):
        exclude = ["id"]
        return [f.name for f in cls._meta.concrete_fields if f.name not in exclude]

    def natural_key(self):
        return self.parent.natural_key() + self.child.natural_key()
    natural_key.dependencies = ["qa.testlist"]

    def __str__(self):
        return "%s -> %s" % (self.parent, self.child)


class UnitTestListManager(models.Manager):
    def by_unit(self, unit):
        return self.get_queryset().filter(unit=unit)

    def by_frequency(self, frequency):
        return self.get_queryset().filter(frequency=frequency)

    def by_unit_frequency(self, unit, frequency):
        return self.by_frequency(frequency).filter(unit=unit)

    def test_lists(self):
        return self.get_queryset().filter(
            content_type=ContentType.objects.get(app_label="qa", model="testlist")
        )

    def by_visibility(self, groups):
        return self.get_queryset().filter(visible_to__in=groups)


class UnitTestCollection(models.Model):
    """keeps track of which units should perform which test lists at a given frequency"""

    unit = models.ForeignKey(Unit)

    frequency = models.ForeignKey(
        Frequency,
        help_text=_("Frequency with which this test list is to be performed"),
        null=True,
        blank=True,
        related_name='unittestcollections'
    )
    due_date = models.DateTimeField(help_text=_("Next time this item is due"), null=True, blank=True)
    auto_schedule = models.BooleanField(
        help_text=_("If this is checked, due_date will be auto set based on the assigned frequency"),
        default=True,
    )

    assigned_to = models.ForeignKey(
        Group,
        help_text=_("QA group that this test list should nominally be performed by"),
        null=True,
    )
    visible_to = models.ManyToManyField(
        Group,
        help_text=_("Select groups who will be able to see this test collection on this unit"),
        related_name="test_collection_visibility",
    )

    active = models.BooleanField(help_text=_("Uncheck to disable this test on this unit"), default=True, db_index=True)

    limit = Q(app_label='qa', model='testlist') | Q(app_label='qa', model='testlistcycle')
    content_type = models.ForeignKey(
        ContentType,
        limit_choices_to=limit,
        verbose_name="Test List or Test List Cycle",
        help_text="Choose whether to use a Test List or Test List Cycle",
    )
    object_id = models.PositiveIntegerField(
        verbose_name="Tests collection",
        help_text="Choose the tests collection object to assign to the unit",
    )
    tests_object = GenericForeignKey("content_type", "object_id")
    objects = UnitTestListManager()
    name = models.CharField(max_length=255, db_index=True, default='', editable=False)

    last_instance = models.ForeignKey("TestListInstance", null=True, editable=False, on_delete=models.SET_NULL)

    class Meta:
        unique_together = ("unit", "frequency", "content_type", "object_id",)
        verbose_name_plural = _("Assign Test Lists to Units")
        # ordering = ("testlist__name","testlistcycle__name",)
        permissions = (
            ("can_view_overview", "Can view program overview"),
            ("can_review_non_visible_tli", "Can view tli and utc not visible to user's groups")
        )

    def calc_due_date(self):
        """return the next due date of this Unit/TestList pair """

        if self.auto_schedule and self.frequency is not None:
            last_valid = self.last_valid_instance()
            if last_valid is None and self.last_instance is not None:
                # Done before but no valid lists
                return timezone.now()
            elif last_valid is not None and last_valid.work_completed:
                return last_valid.work_completed + self.frequency.due_delta()

        # return existing due date (could be None)
        return self.due_date

    def set_due_date(self, due_date=None):
        """Set due date field for this UTC. Note model is not saved to db.
        Saving be done manually"""
        if self.auto_schedule and due_date is None and self.frequency is not None:
            due_date = self.calc_due_date()

        if due_date is not None:
            # use update here instead of save so post_save and pre_save signals are not
            # triggered
            self.due_date = due_date
            UnitTestCollection.objects.filter(pk=self.pk).update(due_date=due_date)

    def due_status(self):
        if not self.due_date:
            return NO_DUE_DATE

        today = timezone.localtime(timezone.now()).date()
        due = timezone.localtime(self.due_date).date()

        if today < due:
            return NOT_DUE

        if self.frequency is not None:
            overdue = due + timezone.timedelta(days=self.frequency.overdue_interval - self.frequency.due_interval)
        else:
            overdue = due + timezone.timedelta(days=1)

        if today < overdue:
            return DUE
        return OVERDUE

    def last_valid_instance(self):
        """ return last test_list_instance with all valid tests """

        try:
            return self.testlistinstance_set.filter(
                in_progress=False,
            ).exclude(testinstance__status__valid=False).latest("work_completed")
        except TestListInstance.DoesNotExist:
            pass

    def last_done_date(self):
        """return date this test list was last performed"""

        if hasattr(self, "last_instance") and self.last_instance is not None:
            return self.last_instance.work_completed

    def unreviewed_instances(self):
        """return a query set of all TestListInstances for this object that have not been fully reviewed"""

        return self.testlistinstance_set.filter(
            testinstance__status__requires_review=True,
        ).distinct().select_related("test_list")

    def unreviewed_test_instances(self):
        """return query set of all TestInstances for this object"""

        return TestInstance.objects.complete().filter(
            unit_test_info__unit=self.unit,
            unit_test_info__test__in=self.tests_object.all_tests()
        )

    def history(self, before=None):

        before = before or timezone.now()

        tlis = TestListInstance.objects.filter(unit_test_collection=self)

        if before is not None:
            tlis = tlis.filter(work_completed__lt=before)

        tlis = tlis.order_by(
            "-work_completed"
        ).prefetch_related(
            "testinstance_set__status",
            "testinstance_set__reference",
            "testinstance_set__tolerance",
            "testinstance_set__unit_test_info",
            "testinstance_set__unit_test_info__unit",
            "testinstance_set__unit_test_info__test",
            "testinstance_set__created_by",
        )[:settings.NHIST]

        dates = tlis.values_list("work_completed", flat=True)

        instances = []
        for test in self.tests_object.ordered_tests():
            test_history = []
            for tli in tlis:
                match = [x for x in tli.testinstance_set.all() if x.unit_test_info.test == test]
                test_history.append(match[0] if match else None)

            instances.append((test, test_history))

        return instances, dates

    def next_list(self):
        """return next list to be completed from tests_object"""

        if not hasattr(self, "last_instance") or not self.last_instance:
            first = self.tests_object.first()
            if not first:
                return None, None
            return 0, first

        return self.tests_object.next_list(self.last_instance.day)

    def get_list(self, day=None):
        """return day and next list to be completed from tests_object"""

        if day is None:
            return self.next_list()

        return self.tests_object.get_list(day)

    def get_absolute_url(self):
        return urlresolvers.reverse("perform_qa", kwargs={"pk": self.pk})

    def copy_references(self, dest_unit):

        all_tests = self.tests_object.all_tests()
        source_unit_test_infos = UnitTestInfo.objects.filter(
            test__in=all_tests, unit=self.unit
        ).select_related(
            "reference", "tolerance"
        )

        for source_uti in source_unit_test_infos:
            UnitTestInfo.objects.filter(
                test=source_uti.test, unit=dest_unit
            ).update(
                reference=source_uti.reference,
                tolerance=source_uti.tolerance
            )

    def __str__(self):
        return self.name

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        self.name = self.tests_object.name
        super(UnitTestCollection, self).save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )


class TestInstanceManager(models.Manager):

    def in_progress(self):
        return super(TestInstanceManager, self).filter(test_list_instance__in_progress=True)

    def complete(self):
        return models.Manager.get_queryset(self).filter(test_list_instance__in_progress=False)


class TestInstance(models.Model):
    """
    Model for storing actual value of a measured test as well as whether
    or not the test passed or failed along with the reference and tolerance
    that pass/fail was based on.
    """

    # review status
    status = models.ForeignKey(TestInstanceStatus)
    review_date = models.DateTimeField(null=True, blank=True, editable=False)
    reviewed_by = models.ForeignKey(User, null=True, blank=True, editable=False)

    # did test pass or fail (or was skipped etc)
    pass_fail = models.CharField(max_length=20, choices=PASS_FAIL_CHOICES, editable=False, db_index=True)

    # values set by user
    value = models.FloatField(
        help_text=_("For boolean Tests a value of 0 equals False and any non zero equals True"),
        null=True,
    )
    string_value = models.CharField(max_length=MAX_STRING_VAL_LEN, null=True, blank=True)

    skipped = models.BooleanField(help_text=_("Was this test skipped for some reason (add comment)"), default=False)
    comment = models.TextField(help_text=_("Add a comment to this test"), null=True, blank=True)

    # reference used
    reference = models.ForeignKey(Reference, null=True, blank=True, editable=False, on_delete=models.SET_NULL)
    tolerance = models.ForeignKey(Tolerance, null=True, blank=True, editable=False, on_delete=models.SET_NULL)

    unit_test_info = models.ForeignKey(UnitTestInfo, editable=False)

    # keep track if this test was performed as part of a test list
    test_list_instance = models.ForeignKey("TestListInstance", editable=False)

    work_started = models.DateTimeField(editable=False, db_index=True)

    # when was the work actually performed
    work_completed = models.DateTimeField(default=timezone.now, help_text=settings.DATETIME_HELP, db_index=True)

    # for keeping a very basic history
    created = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(User, editable=False, related_name="test_instance_creator")
    modified = models.DateTimeField(auto_now=True)
    modified_by = models.ForeignKey(User, editable=False, related_name="test_instance_modifier")

    objects = TestInstanceManager()

    class Meta:
        # ordering = ("work_completed",)
        get_latest_by = "work_completed"
        permissions = (
            ("can_view_history", "Can see test history when performing QA"),
            ("can_view_charts", "Can view charts of test history"),
            ("can_review", "Can review & approve tests"),
            ("can_skip_without_comment", "Can skip tests without comment"),
            ("can_review_own_tests", "Can review & approve  self-performed tests"),
        )

    def save(self, *args, **kwargs):
        self.calculate_pass_fail()
        super(TestInstance, self).save(*args, **kwargs)

    def difference(self):
        """return difference between instance and reference"""
        return self.value - self.reference.value

    def percent_difference(self):
        """return percent difference between instance and reference"""
        if self.reference.value == 0:
            raise ZeroDivisionError("Tried to calculate percent diff with a zero reference value")
        return 100. * (self.value - self.reference.value) / float(self.reference.value)

    def bool_pass_fail(self):
        diff = abs(self.reference.value - self.value)
        if diff > EPSILON:
            if self.tolerance:
                self.pass_fail = TOLERANCE if self.tolerance.bool_warning_only else ACTION
            else:
                self.pass_fail = ACTION
        else:
            self.pass_fail = OK

    def string_pass_fail(self):

        choice = self.string_value.lower()

        if choice in [x.lower() for x in self.tolerance.pass_choices()]:
            self.pass_fail = OK
        elif choice in [x.lower() for x in self.tolerance.tol_choices()]:
            self.pass_fail = TOLERANCE
        else:
            self.pass_fail = ACTION

    def float_pass_fail(self):
        diff = self.calculate_diff()

        t = self.tolerance
        al, tl, th, ah = t.act_low, t.tol_low, t.tol_high, t.act_high
        al = al if al is not None else -1E99
        tl = tl if tl is not None else -1E99
        th = th if th is not None else 1E99
        ah = ah if ah is not None else 1E99

        on_action_border = utils.almost_equal(diff, al) or utils.almost_equal(diff, ah)
        on_tolerance_border = utils.almost_equal(diff, tl) or utils.almost_equal(diff, th)
        inside_action = (al <= diff <= ah) or on_action_border
        inside_tolerance = (tl <= diff <= th) or on_tolerance_border

        if not inside_action:
            self.pass_fail = ACTION
        elif not inside_tolerance:
            self.pass_fail = TOLERANCE
        else:
            self.pass_fail = OK

    def calculate_diff(self):
        if not (self.tolerance and self.reference and self.unit_test_info.test):
            return

        if self.tolerance.type == ABSOLUTE:
            diff = self.difference()
        else:
            diff = self.percent_difference()
        return diff

    def calculate_pass_fail(self):
        """set pass/fail status of the current value"""

        if (
            (self.skipped and not self.unit_test_info.test.hidden) or
            (self.value is None and self.test_list_instance.in_progress)
        ):
            self.pass_fail = NOT_DONE
        elif self.unit_test_info.test.is_boolean() and self.reference:
            self.bool_pass_fail()
        elif self.unit_test_info.test.is_string_type() and self.tolerance:
            self.string_pass_fail()
        elif self.reference and self.tolerance:
            self.float_pass_fail()
        else:
            # no tolerance and/or reference set
            self.pass_fail = NO_TOL

    def get_value(self):
        if self.unit_test_info.test.is_upload():
            return self.attachment_set.first()
        if self.unit_test_info.test.is_string_type():
            return self.string_value
        elif self.unit_test_info.test.is_boolean():
            return bool(self.value)

        return self.value

    def auto_review(self):
        """set review status of the current value if allowed"""
        has_comment = self.comment or self.test_list_instance.comments.all().exists()
        if has_comment and not self.skipped:
            return

        if self.unit_test_info.test.auto_review:
            try:
                self.status = AutoReviewRule.objects.get(pass_fail=self.pass_fail).status
                self.review_date = timezone.now()
            except AutoReviewRule.DoesNotExist:
                pass

    def value_display(self):
        if self.skipped:
            return "Skipped"
        elif self.value is None and self.string_value in (None, ""):
            return NOT_DONE_DISP

        test = self.unit_test_info.test
        if test.is_boolean():
            return "Yes" if int(self.value) == 1 else "No"
        elif test.is_upload():
            return self.upload_link()
        elif test.is_string_type():
            return self.string_value
        return "%.4g" % self.value

    def diff_display(self):
        display = ""
        if self.unit_test_info.test.is_numerical_type() and self.value is not None:
            try:
                diff = self.calculate_diff()
                if diff is not None:
                    display = "%.4g" % diff
                    if self.tolerance and self.tolerance.type == PERCENT:
                        display += "%"
            except ZeroDivisionError:
                display = "Zero ref with % diff tol"
        return display

    def upload_link(self):
        attachment = self.attachment_set.first()
        if attachment is None:
            return None
        name = attachment.attachment.name.split("/")[-1]
        return '<a href="%s" title="%s">%s</a>' % (attachment.attachment.url, name, name)

    def upload_name(self):
        attachment = self.attachment_set.first()
        if attachment is None:
            return None
        return attachment.attachment.name.split("/")[-1]

    def image_url(self):

        attachment = self.attachment_set.first()
        if attachment is None:
            return None

        return attachment.attachment.url

    def __str__(self):
        """return display representation of object"""
        return "TestInstance(pk=%s)" % self.pk


class TestListInstanceManager(models.Manager):

    def unreviewed(self):
        return self.complete().filter(all_reviewed=False).order_by("-work_completed")

    def unreviewed_count(self):
        return self.unreviewed().count()

    def your_unreviewed(self, user):
        return self.complete().filter(
            all_reviewed=False,
            unit_test_collection__visible_to__in=user.groups.all(),
        ).order_by("-work_completed").distinct()

    def your_unreviewed_count(self, user):
        return self.your_unreviewed(user).count()

    def in_progress(self):
        return self.get_queryset().filter(in_progress=True).order_by("-work_completed")

    def complete(self):
        return self.get_queryset().filter(in_progress=False).order_by("-work_completed")

    def user_unreviewed_counts(self):
        return {
            u.id: self.unreviewed().filter(unit_test_collection__visible_to__in=u.groups.all()).distinct().count()
            for u in User.objects.filter(is_active=True)
        }


class TestListInstance(models.Model):
    """Container for a collection of QA :model:`TestInstance`s

    When a user completes a test list, a collection of :model:`TestInstance`s
    are created.  TestListInstance acts as a containter for the collection
    of values so that they are grouped together and can be queried easily.

    """

    unit_test_collection = models.ForeignKey(UnitTestCollection, editable=False)
    test_list = models.ForeignKey(TestList, editable=False)

    work_started = models.DateTimeField(db_index=True)
    work_completed = models.DateTimeField(default=timezone.now, db_index=True, null=True)

    due_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_('When was this session due when it was performed'),
    )

    # comment = models.TextField(help_text=_("Add a comment to this set of tests"), null=True, blank=True)
    comments = GenericRelation(Comment, object_id_field='object_pk')

    in_progress = models.BooleanField(
        help_text=_(
            "Mark this session as still in progress so you can complete later (will not be submitted for review)"
        ),
        default=False,
        db_index=True,
    )

    reviewed = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        User,
        editable=False,
        null=True,
        blank=True,
        related_name="test_list_instance_reviewer",
    )

    all_reviewed = models.BooleanField(default=False)

    day = models.IntegerField(default=0)

    # for keeping a very basic history
    created = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, editable=False, related_name="test_list_instance_creator")
    modified = models.DateTimeField()
    modified_by = models.ForeignKey(User, editable=False, related_name="test_list_instance_modifier")

    objects = TestListInstanceManager()

    class Meta:
        # ordering = ("work_completed",)
        get_latest_by = "work_completed"
        permissions = (
            ("can_override_date", "Can override date"),
            ("can_perform_subset", "Can perform subset of tests"),
            ("can_view_completed", "Can view previously completed instances"),
            ("can_save_in_progress", "Can save test lists as 'In Progress'"),
        )

    def pass_fail_status(self):
        """return string with pass fail status of this qa instance"""
        instances = list(self.testinstance_set.all())
        statuses = [
            (status, display, [x for x in instances if x.pass_fail == status]) for status, display in PASS_FAIL_CHOICES
        ]
        return [x for x in statuses if len(x[2]) > 0]

    def pass_fail_summary(self):
        return {status[0]: len(status[2]) for status in self.pass_fail_status()}

    def duration(self):
        """return timedelta of time from start to completion"""
        return self.work_completed - self.work_started

    def status(self, queryset=None):
        """return string with review status of this qa instance"""
        if queryset is None:
            queryset = self.testinstance_set.prefetch_related("status").all()
        status_types = set([x.status for x in queryset])
        statuses = [(status, [x for x in queryset if x.status == status]) for status in status_types]
        return [x for x in statuses if len(x[1]) > 0]

    def review_summary(self, queryset=None):
        if queryset is None:
            queryset = self.testinstance_set.prefetch_related('status').all()
        comment_count = queryset.exclude(comment='').count() + self.comments.count()

        to_return = {
            status[0].slug: {
                'num': len(status[1]),
                'valid': status[0].valid,
                'reqs_review': status[0].requires_review,
                'default': status[0].is_default,
                'colour': status[0].colour
            } for status in self.status(queryset)
        }
        to_return['Comments'] = {'num': comment_count, 'is_comments': 1}
        return to_return

    def unreviewed_instances(self):
        return self.testinstance_set.filter(status__requires_review=True)

    def update_all_reviewed(self):

        self.all_reviewed = len(self.unreviewed_instances()) == 0

        # use update instead of save so we don't trigger save signal
        TestListInstance.objects.filter(pk=self.pk).update(all_reviewed=self.all_reviewed)

        return self.update_service_event_statuses()

    def update_service_event_statuses(self):
        # set linked service events to default status if not all reviewed.
        changed_se = []
        for rtsqa in self.rtsqa_for_tli.all():
            if not self.all_reviewed and rtsqa.service_event.service_status.rts_qa_must_be_reviewed:
                rtsqa.service_event.service_status = apps.get_model('service_log', 'ServiceEventStatus').get_default()
                rtsqa.service_event.save()
                changed_se.append(rtsqa.service_event_id)

        return changed_se

    def tolerance_tests(self):
        return self.testinstance_set.filter(pass_fail=TOLERANCE)

    def failing_tests(self):
        return self.testinstance_set.filter(pass_fail=ACTION)

    def history(self):
        # note when using, your view should likely prefetch and select related
        # as follows
        # prefetch_related = [
        #     "testinstance_set__unit_test_info__test",
        #     "testinstance_set__reference",
        #     "testinstance_set__tolerance",
        #     "testinstance_set__status",
        # ]
        # select_related = ["unittestcollection__unit"]

        # grab NHIST number of previous results
        tlis = TestListInstance.objects.filter(
            unit_test_collection=self.unit_test_collection,
        )

        if self.work_completed:
            tlis = tlis.filter(
                work_completed__lt=self.work_completed,
            )

        tlis = tlis.order_by(
            "-work_completed"
        ).prefetch_related(
            "testinstance_set__status",
            "testinstance_set__reference",
            "testinstance_set__tolerance",
            "testinstance_set__unit_test_info__test",
            "testinstance_set__unit_test_info__unit",
            "testinstance_set__created_by",
            "testinstance_set__test_list_instance"
        )[:settings.NHIST]

        dates = tlis.values_list("work_completed", flat=True)

        instances = []
        # note sort  here rather than using self.testinstance_set.order_by(("created")
        # because that causes Django to requery db and negates the advantage of using
        # prefetch_related above

        test_instances = sorted(self.testinstance_set.all(), key=lambda x: x.created)
        for ti in test_instances:

            test_history = []
            for tli in tlis:
                q = tli.testinstance_set.all()
                match = [x for x in q if x.unit_test_info_id == ti.unit_test_info_id]
                test_history.append(match[0] if match else None)

            instances.append((ti, test_history))

        return instances, dates

    def get_absolute_url(self):
        return reverse("view_test_list_instance", kwargs={"pk": self.pk})

    def __str__(self):
        return "TestListInstance(pk=%s)" % self.pk

    def str_verbose(self):
        return '%s (%s - %s)' % (
            self.pk, self.test_list.name, timezone.localtime(self.created).strftime('%b %m, %I:%M %p')
        )

    def str_summary(self):
        return '%s (%s%s)' % (
            self.pk,
            timezone.localtime(self.created).strftime('%b %m, %I:%M %p'),
            ' - All reviewed' if self.all_reviewed else ''
        )

    def save(self, *args, **kwargs):
        if self.work_completed and self.work_completed == self.work_started:
            self.work_completed += timezone.timedelta(seconds=60)
        super().save(*args, **kwargs)


class TestListCycleManager(models.Manager):

    def get_by_natural_key(self, slug):
        return self.get(slug=slug)


class TestListCycle(TestCollectionInterface, TestPackMixin):
    """
    A basic model for creating a collection of test lists that cycle
    based on the list that was last completed.
    """

    NK_FIELDS = ['slug']

    DAY = "day"
    TEST_LIST_NAME = "tlname"
    DAY_OPTIONS_TEXT_CHOICES = (
        (DAY, "Day"),
        (TEST_LIST_NAME, "Test List Name"),
    )

    test_lists = models.ManyToManyField(TestList, through="TestListCycleMembership")
    drop_down_label = models.CharField(
        max_length=128,
        default="Choose Day",
        help_text="Text to be shown alongside the drop down list for selecting the cycle day to perform.",
    )
    day_option_text = models.CharField(
        max_length=8,
        choices=DAY_OPTIONS_TEXT_CHOICES,
        default=DAY,
        help_text="Should the drop down show the day number or test list name?",
    )
    utcs = GenericRelation(UnitTestCollection, related_query_name='test_list_cycle')

    objects = TestListCycleManager()

    def __len__(self):
        """return the number of test_lists"""
        if self.pk:
            return self.test_lists.count()
        else:
            return 0

    def test_list_members(self):
        """return all days from this collection"""
        return self.test_lists.all()

    def first(self):
        """return first in order membership obect for this cycle"""
        try:
            return self.testlistcyclemembership_set.all()[0].test_list
        except IndexError:
            return None

    def all_lists(self):
        """return queryset for all children lists of this cycle including sublists"""
        query = TestList.objects.none()
        for test_list in self.test_lists.all():
            query |= test_list.all_lists()

        return query.distinct()

    def all_tests(self):
        """return all test members of cycle members (including sublists)"""
        query = Test.objects.none()
        for test_list in self.test_lists.all():
            query |= test_list.all_tests()
        return query.distinct()

    ordered_tests = all_tests

    def get_list(self, day=0):
        """get actual day and test list for given input day"""
        try:
            membership = self.testlistcyclemembership_set.get(order=day)
            return day, membership.test_list
        except TestListCycleMembership.DoesNotExist:
            return None, None

    def next_list(self, day):
        """return day and test list following input day in cycle order"""

        try:
            return day + 1, self.testlistcyclemembership_set.get(order=day + 1).test_list
        except (TypeError, TestListCycleMembership.DoesNotExist):
            first = self.first()
            if not first:
                return None, None
            return 0, self.first()

    def days_display(self):
        names = self.testlistcyclemembership_set.values_list("test_list__name", flat=True)
        days = list(range(1, len(names) + 1))
        if self.day_option_text == self.TEST_LIST_NAME:
            return list(zip(days, names))

        return [(d, "Day %d" % d) for d in days]

    @classmethod
    def get_testpack_fields(cls):
        exclude = ["id", "created", "created_by", "modified", "modified_by"]
        return [f.name for f in cls._meta.concrete_fields if f.name not in exclude]

    def get_testpack_dependencies(self):

        all_lists = list(self.all_lists())

        sublists = []
        for tl in all_lists:
            sublists += list(tl.sublist_set.all())

        test_list_memberships = []
        for tl in all_lists:
            test_list_memberships += list(tl.testlistmembership_set.all())

        all_tests = list(self.all_tests())

        return [
            (Category, [s.category for s in all_tests]),
            (Test, all_tests),
            (TestListMembership, test_list_memberships),
            (TestList, all_lists),
            (Sublist, sublists),
            (TestListCycleMembership, self.testlistcyclemembership_set.all()),
        ]

    def natural_key(self):
        return (self.slug,)

    def __str__(self):
        return _(self.name)

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        super(TestListCycle, self).save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )
        self.utcs.update(name=self.name)


class TestListCycleMembershipManager(models.Manager):

    def get_by_natural_key(self, test_list_slug, cycle_slug):
        return self.get(test_list__slug=test_list_slug, cycle__slug=cycle_slug)


class TestListCycleMembership(models.Model):
    """M2M model for ordering of test lists within cycle"""

    NK_FIELDS = ['cycle', 'test_list']

    test_list = models.ForeignKey(TestList)
    cycle = models.ForeignKey(TestListCycle)
    order = models.IntegerField()

    objects = TestListCycleMembershipManager()

    class Meta:
        ordering = ("order",)

        # note the following won't actually work because when saving multiple
        # memberships they can have the same order temporarily when orders are changed
        # unique_together = (("order", "cycle"),)

    @classmethod
    def get_testpack_fields(cls):
        exclude = ["id"]
        return [f.name for f in cls._meta.concrete_fields if f.name not in exclude]

    def natural_key(self):
        return self.cycle.natural_key() + self.test_list.natural_key()
    natural_key.dependencies = ["qa.testlistcycle", "qa.testlist"]

    def __str__(self):
        return "TestListCycleMembership(pk=%s)" % self.pk
