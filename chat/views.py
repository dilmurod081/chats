from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.views.decorators.http import require_POST
from django.db.models import Q
from django.db import IntegrityError
from django.conf import settings
import json
import secrets
from .models import Group, Channel, Message, Contact, GroupMember, ChannelMember, Bot, BotScript


# --- Auth Views (Unchanged) ---
def landing_page(request):
    if request.user.is_authenticated: return redirect('chat:index')
    return render(request, 'chat/landing.html')


def login_view(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        user = authenticate(request, username=data.get('username'), password=data.get('password'))
        if user:
            login(request, user)
            return JsonResponse({'success': True})
        return JsonResponse({'error': 'Invalid username or password.'}, status=400)
    return render(request, 'chat/login.html')


def register_view(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        try:
            user = User.objects.create_user(username=data.get('username'), password=data.get('password'))
            login(request, user)
            return JsonResponse({'success': True})
        except IntegrityError:
            return JsonResponse({'error': 'This username is already taken.'}, status=400)
    return render(request, 'chat/register.html')


@login_required
def logout_view(request):
    logout(request)
    return redirect('chat:landing')


# --- Main Chat View ---
@login_required
def chat_index(request):
    contact_users = User.objects.filter(contact_of__user=request.user)
    message_users = User.objects.filter(
        Q(sent_messages__recipient_user=request.user) | Q(received_messages__sender=request.user)
    ).distinct()
    combined_users = list(set(list(contact_users) + list(message_users)))
    direct_message_users = [user for user in combined_users if user.id != request.user.id]

    groups = request.user.chat_groups.all()
    channels = request.user.chat_channels.all()
    bots = request.user.bots.all()

    context = {
        'direct_message_users': direct_message_users,
        'groups': groups,
        'channels': channels,
        'bots': bots,
    }
    return render(request, 'chat/index.html', context)


# --- BotFather & Bot Store Views ---
@login_required
def bot_management_view(request):
    bots = request.user.bots.all()
    return render(request, 'chat/bot_management.html', {'bots': bots})


@login_required
def bot_store_view(request):
    all_bots = Bot.objects.exclude(owner=request.user)
    return render(request, 'chat/bot_store.html', {'all_bots': all_bots})


@login_required
@require_POST
def create_bot(request):
    data = json.loads(request.body)
    username = data.get('username')
    if not username:
        return JsonResponse({'error': 'Bot username is required.'}, status=400)
    if not username.lower().endswith('bot'):
        return JsonResponse({'error': 'Bot username must end with "bot".'}, status=400)

    try:
        bot_user = User.objects.create_user(username=username, password=secrets.token_hex(16))
        bot = Bot.objects.create(owner=request.user, user_account=bot_user)
        return JsonResponse({'success': True, 'username': bot.user_account.username, 'token': bot.token})
    except IntegrityError:
        return JsonResponse({'error': 'This username is already taken.'}, status=400)


@login_required
def get_bot_scripts(request, bot_id):
    bot = get_object_or_404(Bot, id=bot_id, owner=request.user)
    scripts = list(bot.scripts.values('id', 'trigger', 'response'))
    return JsonResponse(scripts, safe=False)


@login_required
@require_POST
def add_bot_script(request, bot_id):
    bot = get_object_or_404(Bot, id=bot_id, owner=request.user)
    data = json.loads(request.body)
    trigger = data.get('trigger')
    response = data.get('response')
    if not trigger or not response:
        return JsonResponse({'error': 'Trigger and response are required.'}, status=400)
    script = BotScript.objects.create(bot=bot, trigger=trigger, response=response)
    return JsonResponse({'success': True, 'id': script.id, 'trigger': script.trigger, 'response': script.response})


@login_required
@require_POST
def delete_bot_script(request, script_id):
    script = get_object_or_404(BotScript, id=script_id, bot__owner=request.user)
    script.delete()
    return JsonResponse({'success': True})


# --- User & Group Management ---
@login_required
def get_item_members(request, item_id):
    item_type = request.GET.get('type')
    members_data = []
    if item_type == 'group':
        group = get_object_or_404(Group, id=item_id)
        if request.user in group.members.all():
            members = group.members.exclude(id=request.user.id)
            members_data = list(members.values('id', 'username'))
    elif item_type == 'channel':
        channel = get_object_or_404(Channel, id=item_id)
        if request.user in channel.members.all():
            members = channel.members.exclude(id=request.user.id)
            members_data = list(members.values('id', 'username'))
    return JsonResponse(members_data, safe=False)


@login_required
@require_POST
def add_contact(request):
    data = json.loads(request.body)
    username_to_add = data.get('username')
    try:
        contact_user_to_add = User.objects.get(username__iexact=username_to_add)
        if contact_user_to_add == request.user:
            return JsonResponse({"error": "You cannot add yourself."}, status=400)

        Contact.objects.get_or_create(user=request.user, contact_user=contact_user_to_add)

        return JsonResponse(
            {"success": True, "contact": {'id': contact_user_to_add.id, 'username': contact_user_to_add.username}})
    except User.DoesNotExist:
        return JsonResponse({"error": "User not found."}, status=404)


@login_required
@require_POST
def create_group_or_channel(request):
    data = json.loads(request.body)
    name = data.get('name')
    type = data.get('type')

    if not name:
        return JsonResponse({'error': 'Name is required.'}, status=400)

    creator_permissions = {
        'can_add_users': True, 'can_delete_messages': True,
        'can_manage_item': True, 'can_promote_members': True,
        'is_admin': True
    }

    if type == 'group':
        item = Group.objects.create(name=name, creator=request.user)
        GroupMember.objects.create(group=item, user=request.user, **creator_permissions)
    elif type == 'channel':
        item = Channel.objects.create(name=name, creator=request.user)
        ChannelMember.objects.create(channel=item, user=request.user, can_send_messages=True, **creator_permissions)
    else:
        return JsonResponse({'error': 'Invalid type.'}, status=400)

    return JsonResponse({'success': True, 'id': item.id, 'name': item.name, 'type': type})


@login_required
@require_POST
def add_member(request, item_id):
    data = json.loads(request.body)
    username_to_add = data.get('username')
    type = data.get('type')

    try:
        user_to_add = User.objects.get(username__iexact=username_to_add)
        if type == 'group':
            item = get_object_or_404(Group, id=item_id)
            if not GroupMember.objects.filter(group=item, user=request.user, can_add_users=True).exists():
                return HttpResponseForbidden("You don't have permission to add members.")
            GroupMember.objects.get_or_create(group=item, user=user_to_add)
        elif type == 'channel':
            item = get_object_or_404(Channel, id=item_id)
            if not ChannelMember.objects.filter(channel=item, user=request.user, can_add_users=True).exists():
                return HttpResponseForbidden("You don't have permission to add members.")
            ChannelMember.objects.get_or_create(channel=item, user=user_to_add)
        else:
            return JsonResponse({'error': 'Invalid type.'}, status=400)

        return JsonResponse({'success': True})
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found.'}, status=404)


@login_required
@require_POST
def manage_item(request, item_id):
    data = json.loads(request.body)
    type = data.get('type')
    new_name = data.get('name')

    if type == 'group':
        item = get_object_or_404(Group, id=item_id)
        if not GroupMember.objects.filter(group=item, user=request.user, can_manage_item=True).exists():
            return HttpResponseForbidden("You don't have permission to manage this group.")
    elif type == 'channel':
        item = get_object_or_404(Channel, id=item_id)
        if not ChannelMember.objects.filter(channel=item, user=request.user, can_manage_item=True).exists():
            return HttpResponseForbidden("You don't have permission to manage this channel.")
    else:
        return HttpResponseBadRequest("Invalid item type")

    if new_name:
        item.name = new_name
        item.save()
        return JsonResponse({'success': True, 'name': item.name})

    return HttpResponseBadRequest("No action specified")


@login_required
@require_POST
def manage_member_role(request, item_id, user_id):
    data = json.loads(request.body)
    type = data.get('type')
    permissions = data.get('permissions', {})

    user_to_manage = get_object_or_404(User, id=user_id)

    if type == 'group':
        item = get_object_or_404(Group, id=item_id)
        if not GroupMember.objects.filter(group=item, user=request.user, can_promote_members=True).exists():
            return HttpResponseForbidden("You don't have permission to manage roles.")
        member, _ = GroupMember.objects.get_or_create(group=item, user=user_to_manage)
    elif type == 'channel':
        item = get_object_or_404(Channel, id=item_id)
        if not ChannelMember.objects.filter(channel=item, user=request.user, can_promote_members=True).exists():
            return HttpResponseForbidden("You don't have permission to manage roles.")
        member, _ = ChannelMember.objects.get_or_create(channel=item, user=user_to_manage)
    else:
        return HttpResponseBadRequest("Invalid item type")

    # Update permissions
    member.is_admin = permissions.get('is_admin', member.is_admin)
    member.can_add_users = permissions.get('can_add_users', member.can_add_users)
    member.can_delete_messages = permissions.get('can_delete_messages', member.can_delete_messages)
    member.can_manage_item = permissions.get('can_manage_item', member.can_manage_item)
    member.can_promote_members = permissions.get('can_promote_members', member.can_promote_members)
    if type == 'channel':
        member.can_send_messages = permissions.get('can_send_messages', member.can_send_messages)

    member.save()
    return JsonResponse({'success': True})


# --- Messaging API Views ---
def execute_bot_logic(message):
    recipient = message.recipient_user or message.recipient_group
    if not recipient or not message.text: return

    bots_to_check = []
    if isinstance(recipient, User) and hasattr(recipient, 'bot_profile'):
        bots_to_check.append(recipient.bot_profile)
    elif isinstance(recipient, Group):
        bots_to_check.extend(recipient.bots.all())

    for bot in bots_to_check:
        for script in bot.scripts.all():
            if script.trigger.lower() in message.text.lower():
                reply_data = {
                    'sender': bot.user_account,
                    'text': script.response
                }
                if isinstance(recipient, User):
                    reply_data['recipient_user'] = message.sender
                else:  # Group
                    reply_data['recipient_group'] = recipient

                Message.objects.create(**reply_data)
                break


@login_required
@require_POST
def send_message(request):
    recipient_type = request.POST.get('type')
    recipient_id = request.POST.get('id')
    text = request.POST.get('text')
    file = request.FILES.get('file')

    if not text and not file:
        return JsonResponse({'error': 'Message must have text or a file.'}, status=400)

    message_data = {'sender': request.user, 'text': text, 'file': file}

    if recipient_type == 'user':
        message_data['recipient_user'] = get_object_or_404(User, id=recipient_id)
    elif recipient_type == 'group':
        group = get_object_or_404(Group, id=recipient_id)
        if not GroupMember.objects.filter(group=group, user=request.user).exists():
            return HttpResponseForbidden("You are not a member of this group.")
        message_data['recipient_group'] = group
    elif recipient_type == 'channel':
        channel = get_object_or_404(Channel, id=recipient_id)
        if not ChannelMember.objects.filter(channel=channel, user=request.user, can_send_messages=True).exists():
            return HttpResponseForbidden("You don't have permission to send messages in this channel.")
        message_data['recipient_channel'] = channel
    else:
        return HttpResponseBadRequest("Invalid recipient type.")

    new_message = Message.objects.create(**message_data)

    if new_message.text:
        execute_bot_logic(new_message)

    return JsonResponse({'success': True})


@login_required
@require_POST
def delete_message(request, message_id):
    message = get_object_or_404(Message, id=message_id)
    can_delete = False
    if message.sender == request.user:
        can_delete = True
    elif message.recipient_group:
        if GroupMember.objects.filter(group=message.recipient_group, user=request.user,
                                      can_delete_messages=True).exists():
            can_delete = True
    elif message.recipient_channel:
        if ChannelMember.objects.filter(channel=message.recipient_channel, user=request.user,
                                        can_delete_messages=True).exists():
            can_delete = True

    if not can_delete:
        return HttpResponseForbidden("You don't have permission to delete this message.")

    message.is_deleted = True
    message.save()
    return JsonResponse({"success": True})
@login_required
def get_messages(request):
    recipient_type = request.GET.get('type')
    recipient_id = request.GET.get('id')
    messages = None

    if recipient_type == 'user':
        other_user = get_object_or_404(User, id=recipient_id)
        messages = Message.objects.filter(
            (Q(sender=request.user) & Q(recipient_user=other_user)) |
            (Q(sender=other_user) & Q(recipient_user=request.user))
        )
    elif recipient_type == 'group':
        group = get_object_or_404(Group, id=recipient_id)
        if not GroupMember.objects.filter(group=group, user=request.user).exists():
            return HttpResponseForbidden("You are not a member of this group.")
        messages = group.messages.all()
    elif recipient_type == 'channel':
        channel = get_object_or_404(Channel, id=recipient_id)
        if not ChannelMember.objects.filter(channel=channel, user=request.user).exists():
            return HttpResponseForbidden("You are not a member of this channel.")
        messages = channel.messages.all()
    else:
        return HttpResponseBadRequest("Invalid recipient type.")

    message_list = list(messages.values('id', 'sender__username', 'text', 'file', 'timestamp', 'is_deleted'))
    for msg in message_list:
        if msg['file']:
            msg['file'] = request.build_absolute_uri(settings.MEDIA_URL + msg['file'])

    return JsonResponse(message_list, safe=False)
@login_required
def find_user(request, username):
    try:
        user = User.objects.get(username__iexact=username)
        return JsonResponse({'id': user.id, 'username': user.username})
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)