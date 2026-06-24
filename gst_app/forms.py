from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone

from .models import EndOfDay, Invoice, Supplier


END_OF_DAY_MONEY_FIELDS = [
    "cash",
    "eftpos",
    "amex_card",
    "fleet_card",
    "motorpass",
    "motorcharge",
    "united_card",
    "iou",
    "drive_offs",
    "vault_drop",
    "uber_eats",
    "doordash",
    "diners_card",
    "store_value_charge",
    "iou_payment",
    "drive_off_payment",
    "total_sales",
    "total_fuel_sales",
    "gross_shop_sales",
    "ezy_pin",
    "less_surcharge",
]

END_OF_DAY_FUEL_DIP_FIELDS = [
    "fuel_dip_1_name",
    "fuel_dip_1_value",
    "fuel_dip_2_name",
    "fuel_dip_2_value",
    "fuel_dip_3_name",
    "fuel_dip_3_value",
    "fuel_dip_4_name",
    "fuel_dip_4_value",
    "fuel_dip_5_name",
    "fuel_dip_5_value",
    "fuel_dip_6_name",
    "fuel_dip_6_value",
]


class DateInput(forms.DateInput):
    input_type = "date"

    def __init__(self, attrs=None):
        super().__init__(attrs=attrs, format="%Y-%m-%d")


class SignupForm(UserCreationForm):
    email = forms.EmailField(required=False)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ("name",)


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = (
            "supplier",
            "invoice_date",
            "invoice_number",
            "invoice_file",
            "entered_by",
            "invoice_amount",
            "notes",
        )
        widgets = {
            "invoice_date": DateInput(),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        today = timezone.localdate()
        self.fields["invoice_date"].initial = (self.instance.invoice_date if self.instance.pk else today).isoformat()
        self.fields["invoice_date"].widget.attrs.update({"min": today.isoformat(), "max": today.isoformat()})
        if user is not None:
            self.fields["supplier"].queryset = Supplier.objects.all()

    def clean_invoice_date(self):
        invoice_date = self.cleaned_data["invoice_date"]
        today = timezone.localdate()
        if invoice_date != today:
            raise forms.ValidationError("Invoice date must be today's date.")
        return invoice_date

    def clean(self):
        cleaned = super().clean()
        supplier = cleaned.get("supplier")
        invoice_number = cleaned.get("invoice_number")
        if self.user and supplier and invoice_number:
            qs = Invoice.objects.filter(
                user=self.user,
                supplier=supplier,
                invoice_number__iexact=invoice_number.strip(),
            )
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error("invoice_number", "This invoice number already exists for this supplier.")
        return cleaned


class EndOfDayForm(forms.ModelForm):
    money_fields = END_OF_DAY_MONEY_FIELDS
    fuel_dip_fields = END_OF_DAY_FUEL_DIP_FIELDS

    class Meta:
        model = EndOfDay
        fields = (
            "date",
            "site_name",
            "entered_by",
            *END_OF_DAY_MONEY_FIELDS,
            *END_OF_DAY_FUEL_DIP_FIELDS,
            "master_sheet_file",
            "end_of_days_file",
            "note",
        )
        widgets = {
            "date": DateInput(),
            "note": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        today = timezone.localdate()
        self.fields["date"].initial = (self.instance.date if self.instance.pk else today).isoformat()
        self.fields["date"].widget.attrs.update({"min": today.isoformat(), "max": today.isoformat()})
        for field in self.money_fields:
            self.fields[field].required = False
            self.fields[field].widget.attrs.update({"step": "0.01", "min": "0"})
        for field in self.fuel_dip_fields:
            self.fields[field].required = True
        for index in range(1, 7):
            name_field = f"fuel_dip_{index}_name"
            value_field = f"fuel_dip_{index}_value"
            self.fields[name_field].label = f"Fuel dip {index}"
            self.fields[name_field].widget.attrs.update({"placeholder": "E85 tank 1"})
            self.fields[value_field].label = f"Dip value {index}"
            self.fields[value_field].widget.attrs.update({"step": "0.01", "min": "0", "placeholder": "0.00"})
        self.fields["vault_drop"].label = "Vault Drop / Cash Drop"
        self.fields["total_sales"].label = "Terminal Total"
        self.fields["master_sheet_file"].label = "Master Sheet"
        self.fields["end_of_days_file"].label = "End Of Days"
        for field in ("master_sheet_file", "end_of_days_file"):
            self.fields[field].required = not bool(self.instance.pk and getattr(self.instance, field))
            self.fields[field].help_text = "Upload a PDF, image, Word, or Excel file. Multi-page PDFs are supported."
            self.fields[field].widget.attrs.update({"accept": ".pdf,.png,.jpg,.jpeg,.gif,.webp,.doc,.docx,.xls,.xlsx"})
        self.fields["gross_shop_sales"].widget.attrs.update({"readonly": "readonly"})
        self.fields["ezy_pin"].required = True
        self.fields["less_surcharge"].required = True

    def clean(self):
        cleaned = super().clean()
        if self.data.get(self.add_prefix("ezy_pin"), "").strip() == "":
            self.add_error("ezy_pin", "EZY Pin is required. Enter 0 if there was no EZY Pin value.")
        if self.data.get(self.add_prefix("less_surcharge"), "").strip() == "":
            self.add_error("less_surcharge", "Less Surcharge is required. Enter 0 if there was no surcharge value.")
        for field in self.money_fields:
            if cleaned.get(field) in (None, ""):
                cleaned[field] = 0
        for field in self.fuel_dip_fields:
            if cleaned.get(field) in (None, ""):
                self.add_error(field, f"{self.fields[field].label} is required.")

        date = cleaned.get("date")
        today = timezone.localdate()
        if date and date != today:
            self.add_error("date", "End of Day date must be today's date.")
        if self.user and date:
            qs = EndOfDay.objects.filter(user=self.user, date=date, archived_at__isnull=True)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                existing = qs.first()
                self.add_error("date", f"An End of Day record already exists for this date. Open record #{existing.pk} to edit it.")

        return cleaned


class InvoiceReportForm(forms.Form):
    supplier = forms.ModelChoiceField(queryset=Supplier.objects.none(), required=False)
    invoice_number = forms.CharField(required=False)
    start_date = forms.DateField(required=False, widget=DateInput())
    end_date = forms.DateField(required=False, widget=DateInput())

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["supplier"].queryset = Supplier.objects.filter(user=user)


class EndOfDayReportForm(forms.Form):
    PERIOD_CHOICES = [
        ("today", "Today"),
        ("yesterday", "Yesterday"),
        ("last_7_days", "Last 7 days"),
        ("last_month", "Last 1 month"),
        ("custom", "Custom range"),
    ]
    period = forms.ChoiceField(choices=PERIOD_CHOICES, required=False)
    start_date = forms.DateField(required=False, widget=DateInput())
    end_date = forms.DateField(required=False, widget=DateInput())
