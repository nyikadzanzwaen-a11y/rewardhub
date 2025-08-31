from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import LoyaltyProgram, Rule, Transaction
from .serializers import LoyaltyProgramSerializer, RuleSerializer, TransactionSerializer
from apps.customers.models import Customer, LoyaltyAccount
from apps.customers.serializers import LoyaltyAccountSerializer, PointAdjustmentSerializer
from apps.locations.models import Location
from apps.locations.serializers import LocationSerializer
from apps.rewards.models import Reward
from apps.rewards.serializers import RewardSerializer
from apps.ai_services.models import ChurnPrediction, OpenAIService
from apps.ai_services.serializers import ChurnPredictionSerializer


# Admin API Views
class LoyaltyProgramListCreateView(generics.ListCreateAPIView):
    serializer_class = LoyaltyProgramSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def get_queryset(self):
        # Filter by tenant if provided in headers
        tenant_id = self.request.headers.get('X-Tenant-ID')
        if tenant_id:
            return LoyaltyProgram.objects.filter(tenant_id=tenant_id)
        return LoyaltyProgram.objects.all()


class LoyaltyProgramDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = LoyaltyProgramSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    queryset = LoyaltyProgram.objects.all()


class RuleListCreateView(generics.ListCreateAPIView):
    serializer_class = RuleSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def get_queryset(self):
        program_id = self.request.query_params.get('program_id')
        if program_id:
            return Rule.objects.filter(program_id=program_id)
        return Rule.objects.all()


class RuleDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = RuleSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    queryset = Rule.objects.all()


class CustomerListView(generics.ListAPIView):
    serializer_class = LoyaltyAccountSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def get_queryset(self):
        tenant_id = self.request.headers.get('X-Tenant-ID')
        if tenant_id:
            return LoyaltyAccount.objects.filter(customer__tenant_id=tenant_id)
        return LoyaltyAccount.objects.all()


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def adjust_customer_points(request, customer_id):
    """Adjust points for a specific customer"""
    serializer = PointAdjustmentSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        customer = get_object_or_404(Customer, id=customer_id)
        points = serializer.validated_data['points']
        description = serializer.validated_data['description']
        
        if points > 0:
            customer.loyalty_account.add_points(points, description)
        else:
            customer.loyalty_account.deduct_points(abs(points), description)
        
        account_serializer = LoyaltyAccountSerializer(customer.loyalty_account)
        return Response(account_serializer.data)
        
    except LoyaltyAccount.DoesNotExist:
        return Response({'error': 'Customer loyalty account not found'}, 
                       status=status.HTTP_404_NOT_FOUND)
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class LocationListCreateView(generics.ListCreateAPIView):
    serializer_class = LocationSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def get_queryset(self):
        tenant_id = self.request.headers.get('X-Tenant-ID')
        if tenant_id:
            return Location.objects.filter(tenant_id=tenant_id)
        return Location.objects.all()


class LocationDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = LocationSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    queryset = Location.objects.all()


class RewardListCreateView(generics.ListCreateAPIView):
    serializer_class = RewardSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def get_queryset(self):
        program_id = self.request.query_params.get('program_id')
        if program_id:
            return Reward.objects.filter(program_id=program_id)
        return Reward.objects.all()


class RewardDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = RewardSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    queryset = Reward.objects.all()


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def analytics_overview(request):
    """Get analytics overview"""
    tenant_id = request.headers.get('X-Tenant-ID')
    
    # Basic analytics data
    customers_count = Customer.objects.filter(tenant_id=tenant_id).count() if tenant_id else Customer.objects.count()
    transactions_count = Transaction.objects.count()
    total_points_issued = Transaction.objects.filter(transaction_type='earn').aggregate(
        total=models.Sum('points')
    )['total'] or 0
    
    data = {
        'customers_count': customers_count,
        'transactions_count': transactions_count,
        'total_points_issued': total_points_issued,
        'active_programs': LoyaltyProgram.objects.filter(active=True).count()
    }
    
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def customer_segments(request):
    """Get customer segmentation insights"""
    ai_service = OpenAIService()
    
    # Get customer data for segmentation
    customers_data = []  # This would be populated with actual customer data
    
    segments = ai_service.segment_customers(customers_data)
    return Response(segments)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def churn_predictions(request):
    """Get churn predictions for customers"""
    tenant_id = request.headers.get('X-Tenant-ID')
    
    queryset = ChurnPrediction.objects.all()
    if tenant_id:
        queryset = queryset.filter(customer__tenant_id=tenant_id)
    
    # Filter by risk level if specified
    risk_level = request.query_params.get('risk_level')
    if risk_level:
        queryset = queryset.filter(risk_level=risk_level)
    
    predictions = queryset.order_by('-churn_risk')[:50]
    serializer = ChurnPredictionSerializer(predictions, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def generate_churn_predictions(request):
    """Generate churn predictions for all customers"""
    tenant_id = request.headers.get('X-Tenant-ID')
    
    customers = Customer.objects.filter(tenant_id=tenant_id) if tenant_id else Customer.objects.all()
    ai_service = OpenAIService()
    
    predictions_created = 0
    for customer in customers[:10]:  # Limit for demo
        try:
            prediction_data = ai_service.predict_churn(customer)
            
            churn_prediction, created = ChurnPrediction.objects.update_or_create(
                customer=customer,
                defaults={
                    'churn_risk': prediction_data['churn_risk'],
                    'factors': prediction_data['factors'],
                    'suggested_actions': prediction_data['suggested_actions']
                }
            )
            
            if created:
                predictions_created += 1
                
        except Exception as e:
            continue
    
    return Response({
        'message': f'Generated {predictions_created} churn predictions',
        'total_processed': min(10, customers.count())
    })