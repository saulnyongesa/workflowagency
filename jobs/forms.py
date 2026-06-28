from django import forms

from .models import JobSubmission


class JobSubmissionForm(forms.ModelForm):
    class Meta:
        model = JobSubmission
        fields = ("text_answer", "proof_url", "proof_file")
        widgets = {
            "text_answer": forms.Textarea(attrs={"rows": 5, "placeholder": "Describe your completed work"}),
            "proof_url": forms.URLInput(attrs={"placeholder": "https://..."}),
        }

    def __init__(self, *args, job=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.job = job
        for field in self.fields.values():
            css_class = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{css_class} form-control".strip()
        if job:
            if job.proof_type == job.ProofType.NONE:
                for field in self.fields.values():
                    field.required = False
            elif job.proof_type == job.ProofType.TEXT:
                self.fields["text_answer"].required = True
                self.fields["proof_url"].required = False
                self.fields["proof_file"].required = False
            elif job.proof_type == job.ProofType.URL:
                self.fields["text_answer"].required = False
                self.fields["proof_url"].required = True
                self.fields["proof_file"].required = False
            elif job.proof_type == job.ProofType.TEXT_URL:
                self.fields["text_answer"].required = True
                self.fields["proof_url"].required = True
                self.fields["proof_file"].required = False
            elif job.proof_type == job.ProofType.FILE:
                self.fields["text_answer"].required = False
                self.fields["proof_url"].required = False
                self.fields["proof_file"].required = True


class RejectionForm(forms.Form):
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), max_length=255)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["reason"].widget.attrs["class"] = "form-control"
