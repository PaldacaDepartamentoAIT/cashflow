"""Registro de auditoría de transacciones (creación, edición, eliminación)."""

from .models import TransactionAuditLog


def serialize_transaction_snapshot(transaction):
    """Instantánea JSON-serializable de los campos relevantes de una transacción,
    tal como estaban en el momento del evento de auditoría."""
    return {
        'date': transaction.date.isoformat() if transaction.date else None,
        'account': str(transaction.account) if transaction.account_id else None,
        'reference_number': transaction.reference_number,
        'description': transaction.description,
        'notes': transaction.notes,
        'categories': [c.name for c in transaction.categories.all()],
        'cost_center': str(transaction.cost_center) if transaction.cost_center_id else None,
        'project': transaction.project.name if transaction.project_id else None,
        'valuation': transaction.valuation.name if transaction.valuation_id else None,
        'status': transaction.get_status_display(),
        'amount_bs': float(transaction.amount_bs),
        'amount_usd': float(transaction.amount_usd),
        'daily_rate': float(transaction.daily_rate),
        'bank_fee_bs': float(transaction.bank_fee_bs),
        'bank_fee_usd': float(transaction.bank_fee_usd),
        'real_dollars': float(transaction.real_dollars) if transaction.real_dollars is not None else None,
        'bank_fee_real_usd': float(transaction.bank_fee_real_usd),
        'amount_eur': float(transaction.amount_eur) if transaction.amount_eur is not None else None,
        'bank_fee_eur': float(transaction.bank_fee_eur),
    }


def log_transaction_audit(transaction, organization, action, user):
    """Crea un TransactionAuditLog con una instantánea del estado actual de la transacción."""
    return TransactionAuditLog.objects.create(
        transaction=transaction,
        organization=organization,
        transaction_description=transaction.description[:255],
        action=action,
        user=user,
        snapshot=serialize_transaction_snapshot(transaction),
    )
