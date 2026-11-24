from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from drf_spectacular.types import OpenApiTypes
from .models import MemberDeposit, MessBazar, MessUtilities, MessCycle
from .services import validate_cycle_conflict


@extend_schema_field(OpenApiTypes.BINARY)
class SwaggerImageField(serializers.ImageField):
    pass


class MemberDepositCreateGetSerializer(serializers.ModelSerializer):
    class Meta:
        model = MemberDeposit
        fields = ['id', 'member', 'add_by', 'amount', 'section', 'deposit_date']
        read_only_fields = ['id', 'add_by', 'deposit_date']


class CreateMessCycleSerializer(serializers.ModelSerializer):
    is_active = serializers.BooleanField(read_only=True)
    is_over = serializers.BooleanField(read_only=True)

    class Meta:
        model = MessCycle
        fields = ['id', 'mess', 'name', 'start_date', 'end_date', 'is_active', 'is_over']
        read_only_fields = ['id', 'mess', 'is_active', 'is_over']

    def validate(self, attrs):
        start_date = attrs.get('start_date', getattr(self.instance, 'start_date', None))
        end_date = attrs.get('end_date', getattr(self.instance, 'end_date', None))

        mess = self.context.get('mess')
        exclude_id = self.instance.pk if self.instance else None

        if mess and start_date and end_date:
            validate_cycle_conflict(mess, start_date, end_date, exclude_id=exclude_id)
        elif start_date and end_date and end_date <= start_date:
            raise serializers.ValidationError({"end_date": "End date must be after start date."})

        return attrs


class MessBazarSerializer(serializers.ModelSerializer):
    product_image = SwaggerImageField(required=False, allow_null=True)

    class Meta:
        model = MessBazar
        fields = ['id', 'mess', 'member', 'product_name', 'product_quantity', 'product_price', 'product_image', 'created_at']
        read_only_fields = ['id', 'mess', 'created_at']


class MessUtilitiesSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessUtilities
        fields = ['id', 'mess', 'utility_name', 'description', 'utility_cost', 'utility_date']
        read_only_fields = ['id', 'mess', 'utility_date']