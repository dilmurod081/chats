# --- chat/urls.py (Updated) ---
from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    # Page rendering views
    path('', views.landing_page, name='landing'),
    path('chat/', views.chat_index, name='index'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('bot_management/', views.bot_management_view, name='bot_management'),
    path('bot_store/', views.bot_store_view, name='bot_store'),

    # API-like views
    path('find_user/<str:username>/', views.find_user, name='find_user'),
    path('get_item_members/<int:item_id>/', views.get_item_members, name='get_item_members'),
    path('create_bot/', views.create_bot, name='create_bot'),
    path('bots/<int:bot_id>/scripts/', views.get_bot_scripts, name='get_bot_scripts'),
    path('bots/<int:bot_id>/scripts/add/', views.add_bot_script, name='add_bot_script'),
    path('scripts/<int:script_id>/delete/', views.delete_bot_script, name='delete_bot_script'),
    path('add_contact/', views.add_contact, name='add_contact'),
    path('create_item/', views.create_group_or_channel, name='create_item'),
    path('add_member/<int:item_id>/', views.add_member, name='add_member'),
    path('manage_item/<int:item_id>/', views.manage_item, name='manage_item'),
    path('manage_member/<int:item_id>/<int:user_id>/', views.manage_member_role, name='manage_member_role'),
    path('get_messages/', views.get_messages, name='get_messages'),
    path('send_message/', views.send_message, name='send_message'),
    path('delete_message/<int:message_id>/', views.delete_message, name='delete_message'),
]