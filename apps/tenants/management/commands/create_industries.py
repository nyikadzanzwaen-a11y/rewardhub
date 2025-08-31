from django.core.management.base import BaseCommand
from apps.tenants.models import Industry


class Command(BaseCommand):
    help = 'Create sample industry categories for tenant registration'

    def handle(self, *args, **options):
        industries = [
            ('Retail & E-commerce', 'Online and offline retail stores, fashion, electronics, home goods'),
            ('Food & Beverage', 'Restaurants, cafes, bars, food delivery, catering services'),
            ('Health & Wellness', 'Gyms, spas, medical practices, wellness centers, pharmacies'),
            ('Automotive', 'Car dealerships, auto repair shops, car washes, automotive services'),
            ('Beauty & Personal Care', 'Salons, barbershops, beauty clinics, cosmetics stores'),
            ('Entertainment & Recreation', 'Cinemas, gaming centers, sports facilities, entertainment venues'),
            ('Travel & Hospitality', 'Hotels, travel agencies, tour operators, vacation rentals'),
            ('Professional Services', 'Consulting, legal services, accounting, real estate, insurance'),
            ('Education & Training', 'Schools, training centers, online courses, tutoring services'),
            ('Technology & Software', 'Software companies, IT services, tech startups, digital agencies'),
            ('Financial Services', 'Banks, credit unions, investment firms, financial advisors'),
            ('Healthcare', 'Hospitals, clinics, dental practices, veterinary services'),
            ('Home & Garden', 'Home improvement, landscaping, interior design, furniture stores'),
            ('Sports & Fitness', 'Sports clubs, fitness centers, outdoor recreation, sports equipment'),
            ('Pet Services', 'Pet stores, veterinary clinics, grooming services, pet boarding'),
            ('Other', 'Industries not listed above')
        ]

        created_count = 0
        for name, description in industries:
            industry, created = Industry.objects.get_or_create(
                name=name,
                defaults={'description': description}
            )
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created industry: {name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Industry already exists: {name}')
                )

        self.stdout.write(
            self.style.SUCCESS(f'Successfully created {created_count} new industries')
        )
