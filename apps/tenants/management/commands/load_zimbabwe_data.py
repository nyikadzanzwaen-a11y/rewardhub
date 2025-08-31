from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.tenants.models import Industry, Tenant, Branch
from apps.customers.models import Customer, CustomerTenantMembership
import random

User = get_user_model()


class Command(BaseCommand):
    help = 'Load test data for Zimbabwe businesses and customers'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Loading Zimbabwe test data...'))
        
        # Create industries
        self.create_industries()
        
        # Create businesses in Zimbabwe
        self.create_zimbabwe_businesses()
        
        # Create customers in Gweru and Harare
        self.create_zimbabwe_customers()
        
        self.stdout.write(self.style.SUCCESS('Successfully loaded Zimbabwe test data!'))

    def create_industries(self):
        """Create relevant industries for Zimbabwe"""
        industries_data = [
            {
                'name': 'Retail & Supermarkets',
                'description': 'Grocery stores, supermarkets, and retail chains'
            },
            {
                'name': 'Restaurants & Food',
                'description': 'Restaurants, cafes, and food service establishments'
            },
            {
                'name': 'Fuel Stations',
                'description': 'Petrol stations and fuel service providers'
            },
            {
                'name': 'Banking & Finance',
                'description': 'Banks, microfinance, and financial services'
            },
            {
                'name': 'Telecommunications',
                'description': 'Mobile networks and communication services'
            },
            {
                'name': 'Healthcare',
                'description': 'Hospitals, clinics, and medical services'
            },
            {
                'name': 'Education',
                'description': 'Schools, colleges, and educational institutions'
            },
            {
                'name': 'Mining & Agriculture',
                'description': 'Mining companies and agricultural businesses'
            }
        ]
        
        for industry_data in industries_data:
            industry, created = Industry.objects.get_or_create(
                name=industry_data['name'],
                defaults={'description': industry_data['description']}
            )
            if created:
                self.stdout.write(f'Created industry: {industry.name}')

    def create_zimbabwe_businesses(self):
        """Create realistic Zimbabwe businesses"""
        businesses_data = [
            # Retail & Supermarkets
            {
                'business_name': 'OK Zimbabwe',
                'subdomain': 'okzimbabwe',
                'industry': 'Retail & Supermarkets',
                'description': 'Leading supermarket chain in Zimbabwe',
                'contact_email': 'loyalty@ok.co.zw',
                'phone': '+263-4-123456',
                'branches': [
                    {'name': 'OK Gweru Main', 'city': 'Gweru', 'address': 'Main Street, Gweru'},
                    {'name': 'OK Harare CBD', 'city': 'Harare', 'address': 'First Street, Harare'},
                    {'name': 'OK Avondale', 'city': 'Harare', 'address': 'Avondale Shopping Centre, Harare'}
                ]
            },
            {
                'business_name': 'Pick n Pay Zimbabwe',
                'subdomain': 'picknpayzw',
                'industry': 'Retail & Supermarkets',
                'description': 'Quality groceries and household items',
                'contact_email': 'rewards@picknpay.co.zw',
                'phone': '+263-4-234567',
                'branches': [
                    {'name': 'Pick n Pay Gweru', 'city': 'Gweru', 'address': 'Midlands Mall, Gweru'},
                    {'name': 'Pick n Pay Sam Levy', 'city': 'Harare', 'address': 'Sam Levy Village, Harare'}
                ]
            },
            # Restaurants & Food
            {
                'business_name': 'Chicken Inn Zimbabwe',
                'subdomain': 'chickeninnzw',
                'industry': 'Restaurants & Food',
                'description': 'Fast food chicken restaurant chain',
                'contact_email': 'loyalty@chickeninn.co.zw',
                'phone': '+263-4-345678',
                'branches': [
                    {'name': 'Chicken Inn Gweru', 'city': 'Gweru', 'address': 'Robert Mugabe Way, Gweru'},
                    {'name': 'Chicken Inn Harare CBD', 'city': 'Harare', 'address': 'Jason Moyo Avenue, Harare'},
                    {'name': 'Chicken Inn Westgate', 'city': 'Harare', 'address': 'Westgate Shopping Centre, Harare'}
                ]
            },
            {
                'business_name': 'Steers Zimbabwe',
                'subdomain': 'steerszw',
                'industry': 'Restaurants & Food',
                'description': 'Flame-grilled burgers and fast food',
                'contact_email': 'rewards@steers.co.zw',
                'phone': '+263-4-456789',
                'branches': [
                    {'name': 'Steers Gweru', 'city': 'Gweru', 'address': 'Ascot Shopping Centre, Gweru'},
                    {'name': 'Steers Eastgate', 'city': 'Harare', 'address': 'Eastgate Mall, Harare'}
                ]
            },
            # Fuel Stations
            {
                'business_name': 'Zuva Petroleum',
                'subdomain': 'zuvapetroleum',
                'industry': 'Fuel Stations',
                'description': 'Leading fuel retailer in Zimbabwe',
                'contact_email': 'loyalty@zuva.co.zw',
                'phone': '+263-4-567890',
                'branches': [
                    {'name': 'Zuva Gweru Central', 'city': 'Gweru', 'address': 'Bulawayo Road, Gweru'},
                    {'name': 'Zuva Harare Airport', 'city': 'Harare', 'address': 'Airport Road, Harare'},
                    {'name': 'Zuva Borrowdale', 'city': 'Harare', 'address': 'Borrowdale Road, Harare'}
                ]
            },
            # Banking & Finance
            {
                'business_name': 'CBZ Bank',
                'subdomain': 'cbzbank',
                'industry': 'Banking & Finance',
                'description': 'Commercial Bank of Zimbabwe',
                'contact_email': 'rewards@cbz.co.zw',
                'phone': '+263-4-678901',
                'branches': [
                    {'name': 'CBZ Gweru Branch', 'city': 'Gweru', 'address': 'Main Street, Gweru'},
                    {'name': 'CBZ Harare Head Office', 'city': 'Harare', 'address': 'Kwame Nkrumah Avenue, Harare'}
                ]
            },
            # Telecommunications
            {
                'business_name': 'Econet Wireless',
                'subdomain': 'econetzw',
                'industry': 'Telecommunications',
                'description': 'Leading mobile network operator',
                'contact_email': 'loyalty@econet.co.zw',
                'phone': '+263-4-789012',
                'branches': [
                    {'name': 'Econet Shop Gweru', 'city': 'Gweru', 'address': 'Leopold Takawira Street, Gweru'},
                    {'name': 'Econet Shop Harare', 'city': 'Harare', 'address': 'Nelson Mandela Avenue, Harare'}
                ]
            }
        ]
        
        for business_data in businesses_data:
            # Create user for business
            email = business_data['contact_email']
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'first_name': business_data['business_name'].split()[0],
                    'last_name': 'Admin',
                    'is_staff': False
                }
            )
            if created:
                user.set_password('password123')
                user.save()
                self.stdout.write(f'Created user: {email}')
            
            # Get industry
            industry = Industry.objects.get(name=business_data['industry'])
            
            # Create tenant
            tenant, created = Tenant.objects.get_or_create(
                subdomain=business_data['subdomain'],
                defaults={
                    'name': business_data['business_name'],
                    'business_name': business_data['business_name'],
                    'owner': user,
                    'industry': industry,
                    'contact_email': business_data['contact_email'],
                    'contact_phone': business_data['phone'],
                    'active': True,
                    'verified': True
                }
            )
            if created:
                self.stdout.write(f'Created tenant: {tenant.business_name}')
                
                # Skip loyalty program creation for now (will be added later)
                
                # Create branches
                for branch_data in business_data['branches']:
                    Branch.objects.create(
                        tenant=tenant,
                        name=branch_data['name'],
                        address=branch_data['address'],
                        city=branch_data['city'],
                        state='',
                        country='Zimbabwe',
                        latitude=random.uniform(-20.5, -17.5),  # Zimbabwe latitude range
                        longitude=random.uniform(25.0, 33.0),   # Zimbabwe longitude range
                        phone=business_data['phone'],
                        manager_name=f'{branch_data["name"]} Manager'
                    )

    def create_zimbabwe_customers(self):
        """Create test customers in Gweru and Harare"""
        customers_data = [
            # Gweru customers
            {
                'email': 'tafadzwa.moyo@gmail.com',
                'first_name': 'Tafadzwa',
                'last_name': 'Moyo',
                'city': 'Gweru',
                'phone': '+263-77-123-4567'
            },
            {
                'email': 'chipo.mukamuri@yahoo.com',
                'first_name': 'Chipo',
                'last_name': 'Mukamuri',
                'city': 'Gweru',
                'phone': '+263-77-234-5678'
            },
            {
                'email': 'blessing.ncube@gmail.com',
                'first_name': 'Blessing',
                'last_name': 'Ncube',
                'city': 'Gweru',
                'phone': '+263-77-345-6789'
            },
            {
                'email': 'precious.sibanda@outlook.com',
                'first_name': 'Precious',
                'last_name': 'Sibanda',
                'city': 'Gweru',
                'phone': '+263-77-456-7890'
            },
            {
                'email': 'tinashe.madziva@gmail.com',
                'first_name': 'Tinashe',
                'last_name': 'Madziva',
                'city': 'Gweru',
                'phone': '+263-77-567-8901'
            },
            # Harare customers
            {
                'email': 'farai.chikwanha@gmail.com',
                'first_name': 'Farai',
                'last_name': 'Chikwanha',
                'city': 'Harare',
                'phone': '+263-77-678-9012'
            },
            {
                'email': 'rumbidzai.mutasa@yahoo.com',
                'first_name': 'Rumbidzai',
                'last_name': 'Mutasa',
                'city': 'Harare',
                'phone': '+263-77-789-0123'
            },
            {
                'email': 'takudzwa.mazvita@gmail.com',
                'first_name': 'Takudzwa',
                'last_name': 'Mazvita',
                'city': 'Harare',
                'phone': '+263-77-890-1234'
            },
            {
                'email': 'nyasha.gumbo@outlook.com',
                'first_name': 'Nyasha',
                'last_name': 'Gumbo',
                'city': 'Harare',
                'phone': '+263-77-901-2345'
            },
            {
                'email': 'tendai.mapfumo@gmail.com',
                'first_name': 'Tendai',
                'last_name': 'Mapfumo',
                'city': 'Harare',
                'phone': '+263-77-012-3456'
            }
        ]
        
        # Get some tenants to assign customers to
        tenants = list(Tenant.objects.filter(active=True, verified=True))
        
        for customer_data in customers_data:
            # Create user
            user, created = User.objects.get_or_create(
                email=customer_data['email'],
                defaults={
                    'first_name': customer_data['first_name'],
                    'last_name': customer_data['last_name']
                }
            )
            if created:
                user.set_password('password123')
                user.save()
                self.stdout.write(f'Created user: {customer_data["email"]}')
                
                # Create customer profile
                customer = Customer.objects.create(
                    user=user,
                    phone=customer_data['phone'],
                    city=customer_data['city'],
                    country='Zimbabwe'
                )
                
                # Assign customer to 2-4 random tenants
                selected_tenants = random.sample(tenants, random.randint(2, 4))
                
                for tenant in selected_tenants:
                    membership = CustomerTenantMembership.objects.create(
                        customer=customer,
                        tenant=tenant,
                        member_id=f'CUST{customer.id.hex[:8].upper()}'
                    )
                    
                    # Skip loyalty account creation for now (will be added later)
                
                self.stdout.write(f'Created customer: {customer_data["first_name"]} {customer_data["last_name"]} in {customer_data["city"]}')
