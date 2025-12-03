""" Use django forms """
from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError

User = get_user_model()


class RegistrationForm(forms.Form):
    """Collect the information needed to register a new user."""

    # Define form fields
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField(max_length=254)
    password1 = forms.CharField(widget=forms.PasswordInput)
    password2 = forms.CharField(widget=forms.PasswordInput)

    # ---------------- form.is_valid() callers ----------------

    # Check if email is already in use
    def clean_email(self):
        """Ensure the submitted email address is unique."""
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email=email).exists():
            raise ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        """Validate matching passwords and enforce complexity."""
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        # Check if passwords match based on password1 being the main password field
        if ((password1) and (password2) and (password1 != password2)):
            self.add_error("password2", "Passwords must match.")

        # Validate the strength of the password
        if password1:
            try:
                password_validation.validate_password(password1)
            except ValidationError as exc:
                self.add_error("password1", exc)

        # Return the cleaned data
        return cleaned_data

    # ---------------- form.is_valid() callers end ----------------

    # Save the user to the database
    def save(self):
        """Persist a new user instance."""
        # Create a new Django auth in the database
        user = User.objects.create_user(
            username=self.cleaned_data["email"],
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password1"],
            first_name=self.cleaned_data["first_name"],
            last_name=self.cleaned_data["last_name"],
        )
        return user

# Allow authenticated users to update their password.
class ChangePasswordForm(forms.Form):
    """Allow authenticated users to update their password."""
    # Old password field for form
    old_password = forms.CharField(widget=forms.PasswordInput)

    # Get new password field (main new pass)
    new_password1 = forms.CharField(
        widget=forms.PasswordInput,
        help_text=password_validation.password_validators_help_text_html(),
    )

    # Get new password field (varify new pass)
    new_password2 = forms.CharField(widget=forms.PasswordInput)

    # Initialize the form with the user instance
    def __init__(self, user, *args, **kwargs):
        """Store the current user for validation."""
        self.user = user
        super().__init__(*args, **kwargs)

# ---------------- form.is_valid() callers ----------------

    # Ensure the provided current password is correct.
    def clean_old_password(self):
        """Verify the submitted old password matches the current one."""

        # Get the old password from inputed data
        old_password = self.cleaned_data.get("old_password")

        # Check if the old password matches the user's current password
        if not old_password or not self.user.check_password(old_password):
            raise ValidationError("Incorrect current password.")
        return old_password

    def clean(self):
        """Validate matching new passwords and complexity."""
        # Get the cleaned data from the form
        cleaned_data = super().clean()

        # Get the new passwords from cleaned data
        new_password1 = cleaned_data.get("new_password1")
        new_password2 = cleaned_data.get("new_password2")

        # Check if the new passwords match
        if new_password1 and new_password2 and new_password1 != new_password2:
            self.add_error("new_password2", "Passwords must match.")

        # Validate the strength of the new password
        if new_password1:
            try:
                password_validation.validate_password(new_password1, self.user)
            except ValidationError as exc:
                self.add_error("new_password1", exc)

        # Return the cleaned data
        return cleaned_data
 # ---------------- form.is_valid() callers end ----------------

    # Save the new password for the user
    def save(self):
        """Persist the new password for the user."""
        # Get new password
        password = self.cleaned_data["new_password1"]

        # Set and save the new password for the user
        self.user.set_password(password)
        self.user.save(update_fields=["password"])

        # Return the user instance
        return self.user


# Allow authenticated users to reset their password via email.
class ResetPasswordForm(forms.Form):
    """Form used in the emailed password reset flow."""

    # Get new password field (main new pass)
    new_password1 = forms.CharField(
        widget=forms.PasswordInput,
        help_text=password_validation.password_validators_help_text_html(),
    )

    # Get new password field (varify new pass)
    new_password2 = forms.CharField(widget=forms.PasswordInput)

    # Initialize the form with the user instance
    def __init__(self, user, *args, **kwargs):
        """Store the target user for validation."""
        self.user = user
        super().__init__(*args, **kwargs)

# ---------------- form.is_valid() callers ----------------

    def clean(self):
        """Validate matching new passwords and enforce validators."""
        # Get the cleaned data from the form
        cleaned_data = super().clean()

        # Get the new passwords from cleaned data
        new_password1 = cleaned_data.get("new_password1")
        new_password2 = cleaned_data.get("new_password2")

        # Check if the new passwords match
        if new_password1 and new_password2 and new_password1 != new_password2:
            self.add_error("new_password2", "Passwords must match.")

        # Validate the strength of the new password
        if new_password1:
            try:
                password_validation.validate_password(new_password1, self.user)
            except ValidationError as exc:
                self.add_error("new_password1", exc)

        # Return the cleaned data
        return cleaned_data
 # ---------------- form.is_valid() callers end ----------------

    # Save the new password for the user
    def save(self):
        """Persist the new password on the user."""
        # Get new password
        password = self.cleaned_data["new_password1"]

        # Set and save the new password for the user
        self.user.set_password(password)
        self.user.save(update_fields=["password"])

        # Return the user instance
        return self.user
