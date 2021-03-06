import os
import requests
from django.contrib import messages
from django.core.files.base import ContentFile
from django.shortcuts import render
from django.views import View
from django.views.generic import FormView, DetailView, UpdateView
from django.shortcuts import render, redirect, reverse
from django.urls import reverse_lazy
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.views import PasswordChangeView
from django.contrib.messages.views import SuccessMessageMixin
from . import forms, models, mixins


class LoginView(mixins.LoggedOutOnlyView, FormView,):

    template_name = "users/login.html"
    form_class = forms.LoginForm

    def form_valid(self, form):
        email = form.cleaned_data.get("email")
        password = form.cleaned_data.get("password")
        user = authenticate(self.request, username=email, password=password)
        if user is not None:
            login(self.request, user)
        return super().form_valid(form)

    def get_success_url(self):
        next_arg = self.request.GET.get("next")
        print(next_arg)
        if next_arg is not None:
            return next_arg
        else:
            return reverse("core:home")

    # def get(self, request):
    #     form = forms.LoginForm()
    #     return render(request, "users/login.html", {"form": form})

    # def post(self, request):
    #     form = forms.LoginForm(request.POST)
    #     if form.is_valid():
    #         email = form.cleaned_data.get("email")
    #         password = form.cleaned_data.get("password")
    #         user = authenticate(request, username=email, password=password)
    #         if user is not None:
    #             login(request, user)
    #             return redirect(reverse("core:home"))
    #     return render(request, "users/login.html", {"form": form})


def log_out(request):
    messages.info(request, "See you later!")
    logout(request)
    return redirect(reverse("core:home"))


class SignUpView(mixins.LoggedOutOnlyView, FormView):
    template_name = "users/signup.html"
    form_class = forms.SignUpForm
    success_url = reverse_lazy("core:home")

    def form_valid(self, form):
        form.save()
        email = form.cleaned_data.get("email")
        password = form.cleaned_data.get("password")
        user = authenticate(self.request, username=email, password=password)
        if user is not None:
            login(self.request, user)
        user.verify_email()
        return super().form_valid(form)


# 이메일 인증시 인증키 DB에 등록하고 홈으로 리다이렉트
def complete_verification(reqeust, key):
    try:
        user = models.User.objects.get(email_secret=key)
        user.email_verified = True
        user.email_secret = ""
        user.save()
        # to do: add success message
    except models.User.DoesNotExist:
        # to do: add error message
        pass
    return redirect(reverse("core:home"))


# 깃허브 소셜로그인
def github_login(request):
    client_id = os.environ.get("GH_ID")
    redirect_uri = "http://127.0.0.1:8000/users/login/github/callback"
    # 깃허브 권한 페이지로 리다이렉트 된다.
    return redirect(
        # 몇 가지 데이터를 필요로 한다.
        f"https://github.com/login/oauth/authorize?client_id={client_id}&redirect_uri={redirect_uri}&scope=read:user"
    )


class GithubException(Exception):
    pass


# 깃허브에서 다시 다음 뷰로 다이렉트 된다.
def github_callback(request):
    try:
        client_id = os.environ.get("GH_ID")
        client_secret = os.environ.get("GH_SECRET")
        code = request.GET.get("code", None)  # 깃허브에서 access token과 바꾸기 위해 주는 코드
        redirect_uri = "http://127.0.0.1:8000/users/login"
        if code is not None:
            # ID, PASSWORD, CODE를 POST한다.
            token_request = requests.post(
                f"https://github.com/login/oauth/access_token?client_id={client_id}&client_secret={client_secret}&code={code}",
                # post하게 되면 github는 우리에게 json을 준다.
                headers={"Accept": "application/json"},
            )
            token_json = token_request.json()
            # Json에 error가 있는 지 확인한다.
            error = token_json.get("error", None)
            # Error가 있다면
            if error is not None:
                raise GithubException("Can't get access token")
            # Error가 없다면
            else:
                # json에서 access token을 가져온다.
                access_token = token_json.get("access_token")
                # access token을 이용하여 github api를 get한다.
                profile_request = requests.get(
                    "https://api.github.com/user",
                    headers={
                        # github에 access token을 보내고
                        "Authorization": f"token {access_token}",
                        # github에서 json을 가져온다.
                        "Accept": "application/json",
                    },
                )
            profile_json = profile_request.json()
            username = profile_json.get("login", None)
            # 받아온 json에 username이 있다면
            if username is not None:
                name = profile_json.get("name")
                email = profile_json.get("email")
                bio = profile_json.get("bio")
                try:
                    user = models.User.objects.get(email=email)
                    # 과거에 로그인한 방법이 github가 아니라면
                    if user.login_method != models.User.LOGIN_GITHUB:
                        # error를 raise한다.
                        raise GithubException(
                            f"please log in with: {user.login_method}"
                        )
                    else:
                        pass
                # 만약 github로 권한을 준 이력이 없다면
                except models.User.DoesNotExist:
                    # 새로운 유저를 DB에 만들자.
                    user = models.User.objects.create(
                        email=email,
                        first_name=name,
                        username=email,
                        bio=bio,
                        login_method=models.User.LOGIN_GITHUB,
                        email_verified=True,
                    )
                    user.set_unusable_password()
                    user.save()
                login(request, user)
                messages.success(request, f"Welcome back {user.first_name}")
                return redirect(reverse("core:home"))
            # 받아온 json에 username이 없다면
            else:
                raise GithubException("Can't get your profile")
        else:
            raise GithubException("Can't get code")
    except GithubException as e:
        messages.error(request, e)
        # send a error message
        return redirect(reverse("users:login"))


def kakao_login(reqeust):
    client_id = os.environ.get("KAKAO_ID")
    redirect_uri = "http://127.0.0.1:8000/users/login/kakao/callback"
    return redirect(
        f"https://kauth.kakao.com/oauth/authorize?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code"
    )


class KakaoException(Exception):
    pass


def kakao_callback(request):
    try:
        code = request.GET.get("code")
        client_id = os.environ.get("KAKAO_ID")
        redirect_uri = "http://127.0.0.1:8000/users/login/kakao/callback"
        token_request = requests.post(
            f"https://kauth.kakao.com/oauth/token?grant_type=authorization_code&client_id={client_id}&redirect_uri={redirect_uri}&code={code}"
        )
        token_json = token_request.json()
        error = token_json.get("error", None)
        if error is not None:
            raise KakaoException("Can't get authorization code")
        access_token = token_json.get("access_token")
        profile_request = requests.get(
            "https://kapi.kakao.com/v2/user/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        profile_json = profile_request.json()
        kakao_account = profile_json.get("kakao_account")
        email = kakao_account.get("email", None)
        if email is None:
            raise KakaoException("Please also give me your email")
        properties = profile_json.get("properties")
        nickname = properties.get("nickname")
        profile_image = properties.get("profile_image")
        try:
            user = models.User.objects.get(email=email)
            if user.login_method != models.User.LOGIN_KAKAO:
                raise KakaoException(f"please log in with: {user.login_method}")
        except models.User.DoesNotExist:
            user = models.User.objects.create(
                email=email,
                username=email,
                first_name=nickname,
                login_method=models.User.LOGIN_KAKAO,
                email_verified=True,
            )
            user.set_unusable_password()
            user.save()
            if profile_image is not None:
                photo_request = requests.get(profile_image)
                user.avatar.save(
                    f"{nickname}-avatar", ContentFile(photo_request.content)
                )
        login(request, user)
        messages.success(request, f"Welcome back {user.first_name}")
        return redirect(reverse("core:home"))
    except KakaoException as e:
        messages.error(request, e)
        return redirect(reverse("users:login"))


class UserUserView(DetailView):
    model = models.User
    context_object_name = "user_obj"


class UpdateProfileView(mixins.LoggedOnlyView, SuccessMessageMixin, UpdateView):
    model = models.User
    template_name = "users/update-profile.html"
    success_message = "Profile Updated"
    fields = (
        "last_name",
        "first_name",
        # "avatar",
        "gender",
        "bio",
        "birthdate",
        "language",
        "currency",
    )

    def get_object(self, queryset=None):
        return self.request.user

    def get_form(self, form_class=None):
        form = super().get_form(form_class=form_class)
        form.fields["first_name"].widget.attrs = {"placeholder": "Fist name"}
        form.fields["last_name"].widget.attrs = {"placeholder": "Last name"}
        form.fields["gender"].widget.attrs = {"placeholder": "Gender"}
        form.fields["bio"].widget.attrs = {"placeholder": "Bio"}
        form.fields["birthdate"].widget.attrs = {"placeholder": "Birthdate"}
        return form


class UpdatePasswordView(mixins.EmailLoginOnlyView, mixins.LoggedOnlyView, SuccessMessageMixin, PasswordChangeView):
    template_name = "users/change-password.html"
    success_message = "Password Updated"

    def get_form(self, form_class=None):
        form = super().get_form(form_class=form_class)
        form.fields["old_password"].widget.attrs = {"placeholder": "Old Password"}
        form.fields["new_password1"].widget.attrs = {"placeholder": "New Password"}
        form.fields["new_password2"].widget.attrs = {"placeholder": "Confirm New Password"}
        return form

    def get_success_url(self):
        return self.request.user.get_absolute_url()

