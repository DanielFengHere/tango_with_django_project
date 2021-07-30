from datetime import datetime

from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse

from rango.forms import CategoryForm, PageForm, UserForm, UserProfileForm
from rango.models import Category, Page


def register(request):
    registered = False
    if request.method == 'POST':
        user_form = UserForm(request.POST)
        profile_form = UserProfileForm(request.POST)
        if user_form.is_valid() and profile_form.is_valid():
            user = user_form.save()
            user.set_password(user.password)
            user.save()
            profile = profile_form.save(commit=False)
            profile.user = user
            if 'picture' in request.FILES:
                profile.picture = request.FILES['picture']
            profile.save()
            registered = True
        else:
            print(user_form.errors, profile_form.errors)
    else:
        user_form = UserForm()
        profile_form = UserProfileForm()
    return render(request,
                  'rango/register.html',
                  context = {'user_form': user_form,
                             'profile_form': profile_form,
                             'registered': registered})


def user_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(username=username, password=password)
        if user:
            # Is the account active? It could have been disabled.
            if user.is_active:
                # If the account is valid and active, we can log the user in.
                # We'll send the user back to the homepage.
                login(request, user)
                return redirect(reverse('rango:index'))
            else:
                # An inactive account was used - no logging in!
                return HttpResponse("Your Rango account is disabled.")
        else:
            # Bad login details were provided. So we can't log the user in.
            print(f"Invalid login details: {username}, {password}")
            return HttpResponse("Invalid login details supplied.")
    else:
        # No context variables to pass to the template system, hence the
        # blank dictionary object...
        return render(request, 'rango/login.html')


def index(request):
    request.session.set_test_cookie()
    # 查询数据库，获取目前存储的所有分类
    # 按点赞次数倒序排列分类
    # 获取前 5 个分类（如果分类数少于 5 个，那就获取全部）
    # 把分类列表放入 context_dict 字典
    # 稍后传给模板引擎
    category_list = Category.objects.order_by('-likes')[:5]
    page_list = Page.objects.order_by('-views')[:5]
    context_dict = {'categories': category_list, 'pages': page_list}

    visitor_cookie_handler(request)
    context_dict['visits'] = request.session['visits']
    response = render(request, 'rango/index.html', context=context_dict)

    # 渲染响应，发给客户端
    return response


def get_server_side_cookie(request, cookie, default_val=None):
    val = request.session.get(cookie)
    if not val:
        val = default_val
    return val


def show_category(request, category_name_slug):
    # 创建上下文字典，稍后传给模板渲染引擎
    context_dict = {}
    try:
        # 能通过传入的分类别名找到对应的分类吗？
        # 如果找不到，.get() 方法抛出 DoesNotExist 异常
        # 因此 .get() 方法返回一个模型实例或抛出异常
        category = Category.objects.get(slug=category_name_slug)
        # 检索关联的所有网页
        # 注意，filter() 返回一个网页对象列表或空列表
        pages = Page.objects.filter(category=category)
        # 把得到的列表赋值给模板上下文中名为 pages 的键
        context_dict['pages'] = pages
        # 也把从数据库中获取的 category 对象添加到上下文字典中
        # 我们将在模板中通过这个变量确认分类是否存在
        context_dict['category'] = category
    except Category.DoesNotExist:
        # 没找到指定的分类时执行这里
        # 什么也不做
        # 模板会显示消息，指明分类不存在
        context_dict['category'] = None
        context_dict['pages'] = None
    # 渲染响应，返回给客户端
    return render(request, 'rango/category.html', context_dict)


def add_category(request):
    form = CategoryForm()
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            cat = form.save(commit=True)
            print(cat, cat.slug)
            return redirect('/rango/')
        else:

            print(form.errors)
    return render(request, 'rango/add_category.html', {'form': form})


def add_page(request, category_name_slug):
    try:
        category = Category.objects.get(slug=category_name_slug)
    except Category.DoesNotExist:
        category = None
    if category is None:
        return redirect('/rango/')
    form = PageForm()
    if request.method == 'POST':
        form = PageForm(request.POST)
        if form.is_valid():
            if category:
                page = form.save(commit=False)
                page.category = category
                page.views = 0
                page.save()
                return redirect(reverse('rango:show_category', kwargs={'category_name_slug': category_name_slug}))
            else:
                print(form.errors)
    context_dict = {'form': form, 'category': category}
    return render(request, 'rango/add_page.html', context=context_dict)


def about(request):
    if request.session.test_cookie_worked():
        print("TEST COOKIE WORKED!")
    request.session.delete_test_cookie()
    # prints out whether the method is a GET or a POST
    print(request.method)
    # prints out the user name, if no one is logged in it prints `AnonymousUser`
    print(request.user)
    context_cookie = {}
    visitor_cookie_handler(request)
    context_cookie['visits'] = request.session['visits']
    response = render(request, 'rango/about.html', context=context_cookie)

    # 渲染响应，发给客户端
    return response


@login_required
def restricted(request):
    return render(request, 'rango/restricted.html')


@login_required
def user_logout(request):
    # Since we know the user is logged in, we can now just log them out.
    logout(request)
    # Take the user back to the homepage.
    return redirect(reverse('rango:index'))


def visitor_cookie_handler(request):
    visits = int(get_server_side_cookie(request, 'visits', '1'))
    last_visit_cookie = get_server_side_cookie(request,
                                               'last_visit',
                                               str(datetime.now()))
    last_visit_time = datetime.strptime(last_visit_cookie[:-7],
                                        '%Y-%m-%d %H:%M:%S')
    # If it's been more than a day since the last visit...
    if (datetime.now() - last_visit_time).days > 0:
        visits = visits + 1
        # Update the last visit cookie now that we have updated the count
        request.session['last_visit'] = str(datetime.now())
    else:
        # Set the last visit cookie
        request.session['last_visit'] = last_visit_cookie
    # Update/set the visits cookie
    request.session['visits'] = visits