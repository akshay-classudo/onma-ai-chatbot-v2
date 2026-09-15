from django import forms

from .models import LANGUAGE_CHOICES


class AddFromUrlForm(forms.Form):
    url = forms.URLField(
        label="Page URL", max_length=500,
        widget=forms.URLInput(attrs={"placeholder": "https://www.onmascout.de/..."}),
    )
    language = forms.ChoiceField(choices=LANGUAGE_CHOICES, initial="de")
    category = forms.CharField(
        max_length=100, required=False,
        help_text="Optional grouping, e.g. SEO/SEA/Webdesign/Standort.",
    )
    reindex_now = forms.BooleanField(
        required=False, initial=True,
        label="Chunk + embed immediately",
        help_text="Uncheck to only save the entry — reindex later from the list (select it, "
                   "then run “Reindex embeddings for selected entries”).",
    )
