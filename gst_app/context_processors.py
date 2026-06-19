from .models import account_role, is_manager


def account_permissions(request):
    return {
        "account_role": account_role(request.user),
        "can_manage_dayend": is_manager(request.user),
    }
