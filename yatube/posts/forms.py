from django import forms

from .models import Comment, Post


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ('image', 'title', 'text', 'group',)


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ('text',)
