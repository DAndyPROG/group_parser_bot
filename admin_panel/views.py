from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, logout
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from .models import Category, Message, Channel
from .forms import ChannelForm, CategoryForm, MessageForm

def index_view(request):
    category_id = request.GET.get('category')
    count = int(request.GET.get('count', 5))
    
    categories = Category.objects.all()
    
    if category_id and category_id != 'None':
        # If a category is specified, filter messages
        messages_list = Message.objects.filter(
            channel__category_id=category_id
        ).order_by('-created_at')[:count]
    else:
        # Otherwise, get all messages
        messages_list = Message.objects.all().order_by('-created_at')[:count]
    
    context = {
        'categories': categories,
        'messages': messages_list,
        'selected_category': category_id if category_id and category_id != 'None' else '',
        'current_count': count
    }
    
    return render(request, 'admin_panel/index.html', context)


def login_view(request):
    if request.user.is_authenticated:
        return redirect('admin_panel')
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = authenticate(
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password']
            )
            login(request, user)
            return redirect('admin_panel')
    else:
        form = AuthenticationForm()
    return render(request, 'admin_panel/login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('index')

@login_required
def admin_panel_view(request):
    channels_count = Channel.objects.count()
    categories_count = Category.objects.count()
    active_channels_count = Channel.objects.filter(is_active=True).count()
    messages_count = Message.objects.count()
    latest_messages = Message.objects.order_by('-created_at')
    return render(
        request, 
        'admin_panel/admin_panel.html', 
        {'channels_count': channels_count, 
         'categories_count': categories_count, 
         'active_channels_count': active_channels_count, 
         'messages_count': messages_count,
         'latest_messages': latest_messages})

@login_required
def channels_list_view(request):
    channels = Channel.objects.all()
    return render(request, 'admin_panel/channels_list.html', {'channels': channels})

@login_required
def channel_create_view(request):
    categories = Category.objects.all()
    if request.method == 'POST':
        form = ChannelForm(request.POST)
        if form.is_valid():
            channel = form.save()
            messages.success(request, 'Channel successfully created.')
            return redirect('channels_list')
    else:
        form = ChannelForm()
    
    return render(request, 'admin_panel/channel_form.html', {
        'form': form,
        'categories': categories,
        'title': 'Create channel'
    })

@login_required
def channel_detail_view(request, channel_id):
    channel = Channel.objects.get(id=channel_id)
    return render(request, 'admin_panel/channel_detail.html', {'channel': channel})

@login_required
def channel_update_view(request, channel_id):
    channel = get_object_or_404(Channel, pk=channel_id)
    categories = Category.objects.all()
    if request.method == 'POST':
        form = ChannelForm(request.POST, instance=channel)
        if form.is_valid():
            channel = form.save()
            messages.success(request, 'Channel successfully updated.')
            return redirect('channels_list')
    else:
        form = ChannelForm(instance=channel)
    
    return render(request, 'admin_panel/channel_form.html', {
        'form': form,
        'channel': channel,
        'categories': categories,
        'title': 'Update channel'
    })

@login_required
def channel_delete_view(request, channel_id):
    channel = Channel.objects.get(id=channel_id)
    channel.delete()
    return redirect('channels_list')

@login_required
def categories_list_view(request):
    categories = Category.objects.all()
    return render(request, 'admin_panel/categories_list.html', {'categories': categories})

@login_required
def category_create_view(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            category = form.save()
            messages.success(request, 'Category successfully created.')
            return redirect('categories_list')
    else:
        form = CategoryForm()   
    return render(request, 'admin_panel/category_form.html', {
        'form': form,
        'title': 'Create category'
    })

@login_required
def category_detail_view(request, category_id):
    category = get_object_or_404(Category, pk=category_id)
    return render(request, 'admin_panel/category_detail.html', {'category': category})

@login_required
def category_update_view(request, category_id):
    category = get_object_or_404(Category, pk=category_id)
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            category = form.save()
            messages.success(request, 'Category successfully updated.')
            return redirect('categories_list')
    else:
        form = CategoryForm(instance=category)  
    return render(request, 'admin_panel/category_form.html', {
        'form': form,
        'category': category,
        'title': 'Update category'
    })

@login_required
def category_delete_view(request, category_id):
    category = get_object_or_404(Category, pk=category_id)
    category.delete()
    return redirect('categories_list')

@login_required
def messages_list_view(request):
    messages = Message.objects.all()
    return render(request, 'admin_panel/messages_list.html', {'messages': messages})

@login_required
def message_detail_view(request, message_id):
    message = get_object_or_404(Message, pk=message_id)
    return render(request, 'admin_panel/message_detail.html', {'message': message}) 

@login_required
def message_delete_view(request, message_id):
    message = get_object_or_404(Message, pk=message_id)
    message.delete()
    return redirect('messages_list')
