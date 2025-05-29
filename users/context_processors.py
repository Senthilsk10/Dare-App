def user_context(request):
    """
    Add user-specific context to all templates.
    """
    context = {}
    
    if hasattr(request, 'user') and request.user.is_authenticated:
        user = request.user
        context.update({
            'is_admin': user.is_admin,
            'is_hod': user.is_hod,
            'is_guide': user.is_guide,
            'is_student': user.is_student,
            'dark_mode': request.session.get('dark_mode', False),
        })
        
        # Add user's full name and profile picture if available
        if user.first_name and user.last_name:
            context['user_full_name'] = f"{user.first_name} {user.last_name}"
        else:
            context['user_full_name'] = user.username
            
        if hasattr(user, 'profile_picture') and user.profile_picture:
            context['user_profile_picture'] = user.profile_picture.url
            
    return context
