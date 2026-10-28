"""
Input Validation Schemas
Marshmallow schemas for all API endpoints.

Senior Quant Developer Implementation:
- Type validation and coercion
- Business rule validation
- Automatic error messages
- Industry-standard patterns
"""
from marshmallow import Schema, fields, validates, validates_schema, ValidationError
from typing import Any


# ==================== TRADING SCHEMAS ====================

class ProposalRequestSchema(Schema):
    """Validate contract proposal requests."""
    contract_type = fields.Str(required=True)
    symbol = fields.Str(required=True)
    duration = fields.Int(required=True, strict=True)
    duration_unit = fields.Str(required=True)
    amount = fields.Float(required=True, strict=True)
    basis = fields.Str(missing='stake')  # 'stake' or 'payout'
    currency = fields.Str(missing='USD')
    barrier = fields.Str(allow_none=True)
    barrier2 = fields.Str(allow_none=True)
    
    @validates('amount')
    def validate_amount(self, value):
        if value < 0.35:
            raise ValidationError('Minimum stake is $0.35')
        if value > 50000:
            raise ValidationError('Maximum stake is $50,000')
    
    @validates('duration')
    def validate_duration(self, value):
        if value <= 0:
            raise ValidationError('Duration must be positive')
    
    @validates('duration_unit')
    def validate_duration_unit(self, value):
        valid_units = {'t', 's', 'm', 'h', 'd'}
        if value not in valid_units:
            raise ValidationError(f'Duration unit must be one of: {", ".join(valid_units)}')


class BuyContractSchema(Schema):
    """Validate buy contract requests."""
    proposal_id = fields.Str(required=True)
    price = fields.Float(required=True, strict=True)
    
    @validates('price')
    def validate_price(self, value):
        if value <= 0:
            raise ValidationError('Price must be positive')


class SellContractSchema(Schema):
    """Validate sell contract requests."""
    contract_id = fields.Int(required=True, strict=True)
    price = fields.Float(required=True, strict=True)
    
    @validates('price')
    def validate_price(self, value):
        if value <= 0:
            raise ValidationError('Price must be positive')


# ==================== STRATEGY/TRADING SYSTEM SCHEMAS ====================

class TradingSystemCreateSchema(Schema):
    """Validate trading system creation."""
    name = fields.Str(required=True)
    description = fields.Str(allow_none=True)
    symbol = fields.Str(required=True)
    contract_type = fields.Str(required=True)
    duration = fields.Int(required=True, strict=True)
    duration_unit = fields.Str(required=True)
    entry_strategy_type = fields.Str(required=True)
    entry_strategy_config = fields.Dict(required=True)
    exit_strategy_type = fields.Str(required=True)
    exit_strategy_config = fields.Dict(required=True)
    position_sizing_type = fields.Str(required=True)
    position_sizing_config = fields.Dict(required=True)
    
    @validates('name')
    def validate_name(self, value):
        if len(value) < 3:
            raise ValidationError('Name must be at least 3 characters')
        if len(value) > 100:
            raise ValidationError('Name must not exceed 100 characters')
    
    @validates('duration')
    def validate_duration(self, value):
        if value <= 0:
            raise ValidationError('Duration must be positive')


class TradingSystemUpdateSchema(Schema):
    """Validate trading system updates."""
    name = fields.Str()
    description = fields.Str(allow_none=True)
    symbol = fields.Str()
    contract_type = fields.Str()
    duration = fields.Int(strict=True)
    duration_unit = fields.Str()
    entry_strategy_config = fields.Dict()
    exit_strategy_config = fields.Dict()
    position_sizing_config = fields.Dict()
    is_active = fields.Bool()


# ==================== BOT SCHEMAS ====================

class BotConfigSchema(Schema):
    """Validate bot configuration."""
    max_concurrent_trades = fields.Int(strict=True, missing=3)
    trade_interval_seconds = fields.Int(strict=True, missing=60)
    auto_restart_on_error = fields.Bool(missing=True)
    enable_notifications = fields.Bool(missing=True)
    
    @validates('max_concurrent_trades')
    def validate_max_concurrent(self, value):
        if value < 1:
            raise ValidationError('Must allow at least 1 concurrent trade')
        if value > 10:
            raise ValidationError('Maximum 10 concurrent trades allowed')
    
    @validates('trade_interval_seconds')
    def validate_interval(self, value):
        if value < 5:
            raise ValidationError('Minimum interval is 5 seconds')
        if value > 3600:
            raise ValidationError('Maximum interval is 1 hour')


class BotTradingSystemsSchema(Schema):
    """Validate bot trading systems assignment."""
    trading_system_ids = fields.List(fields.Str(), required=True)
    
    @validates('trading_system_ids')
    def validate_systems(self, value):
        if not value:
            raise ValidationError('At least one trading system required')
        if len(value) > 10:
            raise ValidationError('Maximum 10 trading systems allowed')


# ==================== RISK MANAGEMENT SCHEMAS ====================

class RiskLimitsSchema(Schema):
    """Validate risk limits configuration."""
    max_daily_loss = fields.Float(strict=True)
    max_daily_profit = fields.Float(strict=True, allow_none=True)
    max_concurrent_trades = fields.Int(strict=True)
    max_trade_size = fields.Float(strict=True)
    min_trade_size = fields.Float(strict=True)
    max_stake_percentage = fields.Float(strict=True)
    stop_on_daily_loss = fields.Bool(missing=True)
    stop_on_daily_profit = fields.Bool(missing=False)
    require_confirmation = fields.Bool(missing=True)
    
    @validates('max_daily_loss')
    def validate_max_daily_loss(self, value):
        if value is not None and value <= 0:
            raise ValidationError('Max daily loss must be positive')
    
    @validates('max_stake_percentage')
    def validate_stake_percentage(self, value):
        if value <= 0 or value > 100:
            raise ValidationError('Stake percentage must be between 0 and 100')
    
    @validates_schema
    def validate_trade_size_range(self, data, **kwargs):
        min_size = data.get('min_trade_size')
        max_size = data.get('max_trade_size')
        
        if min_size and max_size and min_size > max_size:
            raise ValidationError('Min trade size cannot exceed max trade size')


# ==================== ANALYTICS SCHEMAS ====================

class AnalyticsSyncSchema(Schema):
    """Validate analytics sync parameters."""
    days_back = fields.Int(strict=True, missing=90)
    batch_size = fields.Int(strict=True, missing=500)
    
    @validates('days_back')
    def validate_days_back(self, value):
        if value < 1:
            raise ValidationError('Days back must be at least 1')
        if value > 365:
            raise ValidationError('Maximum days back is 365')
    
    @validates('batch_size')
    def validate_batch_size(self, value):
        if value < 10:
            raise ValidationError('Minimum batch size is 10')
        if value > 1000:
            raise ValidationError('Maximum batch size is 1000')


class TimeframeQuerySchema(Schema):
    """Validate timeframe query parameters."""
    timeframe = fields.Str(missing='daily')
    
    @validates('timeframe')
    def validate_timeframe(self, value):
        valid_timeframes = {'hourly', 'daily', 'all', '1H', '4H', '1D', '1W', '1M', 'All'}
        if value not in valid_timeframes:
            raise ValidationError(f'Invalid timeframe. Must be one of: {", ".join(valid_timeframes)}')


# ==================== PAGINATION SCHEMAS ====================

class PaginationSchema(Schema):
    """Validate pagination parameters."""
    limit = fields.Int(strict=True, missing=50)
    offset = fields.Int(strict=True, missing=0)
    
    @validates('limit')
    def validate_limit(self, value):
        if value < 1:
            raise ValidationError('Limit must be at least 1')
        if value > 500:
            raise ValidationError('Maximum limit is 500')
    
    @validates('offset')
    def validate_offset(self, value):
        if value < 0:
            raise ValidationError('Offset cannot be negative')


# ==================== HELPER FUNCTIONS ====================

def validate_request_data(schema_class: type[Schema], data: dict) -> tuple[dict, dict]:
    """
    Validate request data against a schema.
    
    Args:
        schema_class: Marshmallow schema class
        data: Request data to validate
        
    Returns:
        (validated_data, errors) tuple
        If errors is empty dict, validation passed
        
    Example:
        validated, errors = validate_request_data(ProposalRequestSchema, request.json)
        if errors:
            return jsonify({'errors': errors}), 400
    """
    schema = schema_class()
    try:
        validated_data = schema.load(data)
        return validated_data, {}
    except ValidationError as err:
        return {}, err.messages
