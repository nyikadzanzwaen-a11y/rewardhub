from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from .models import Customer, CustomerTenantMembership
from apps.tenants.models import Tenant

# Use the project's custom user model
User = get_user_model()

class CustomerRegistrationForm(UserCreationForm):
    """Form for customer self-registration"""
    
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    email = forms.EmailField(required=True)
    phone = forms.CharField(max_length=20, required=False)
    date_of_birth = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone', 'date_of_birth', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add styling to all fields
        for field_name, field in self.fields.items():
            field.widget.attrs.update({
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500'
            })

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['email']
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        
        if commit:
            user.save()
            # Create customer profile
            Customer.objects.create(
                user=user,
                phone=self.cleaned_data.get('phone', ''),
                date_of_birth=self.cleaned_data.get('date_of_birth')
            )
        return user


class TenantSelectionForm(forms.Form):
    """Form for selecting tenants to join"""
    
    def __init__(self, *args, **kwargs):
        customer = kwargs.pop('customer', None)
        super().__init__(*args, **kwargs)
        
        # Get available tenants (exclude ones customer is already member of)
        available_tenants = Tenant.objects.filter(active=True, verified=True)
        if customer:
            joined_tenant_ids = customer.tenant_memberships.values_list('tenant_id', flat=True)
            available_tenants = available_tenants.exclude(id__in=joined_tenant_ids)
        
        # Create checkbox field for each available tenant
        for tenant in available_tenants:
            self.fields[f'tenant_{tenant.id}'] = forms.BooleanField(
                required=False,
                label=tenant.business_name,
                widget=forms.CheckboxInput(attrs={
                    'class': 'h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded'
                })
            )
            # Store tenant info for display
            setattr(self, f'tenant_{tenant.id}_info', {
                'id': tenant.id,
                'name': tenant.business_name,
                'industry': tenant.industry.name if tenant.industry else 'N/A',
                'description': tenant.industry.description if tenant.industry else '',
                'subdomain': tenant.subdomain
            })

    def get_selected_tenants(self):
        """Get list of selected tenant IDs"""
        selected = []
        for field_name, value in self.cleaned_data.items():
            if field_name.startswith('tenant_') and value:
                tenant_id = field_name.replace('tenant_', '')
                selected.append(tenant_id)
        return selected


class CustomerProfileForm(forms.ModelForm):
    """Form for updating customer profile"""
    
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    email = forms.EmailField(required=True)
    
    class Meta:
        model = Customer
        fields = ['phone', 'date_of_birth', 'address', 'city', 'state', 'postal_code', 'country']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'address': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add styling to all fields
        for field_name, field in self.fields.items():
            field.widget.attrs.update({
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500'
            })
        
        # Pre-populate user fields if instance exists
        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['email'].initial = self.instance.user.email

    def save(self, commit=True):
        customer = super().save(commit=False)
        
        # Update user fields
        if customer.user:
            customer.user.first_name = self.cleaned_data['first_name']
            customer.user.last_name = self.cleaned_data['last_name']
            customer.user.email = self.cleaned_data['email']
            customer.user.username = self.cleaned_data['email']
            if commit:
                customer.user.save()
        
        if commit:
            customer.save()
        return customer