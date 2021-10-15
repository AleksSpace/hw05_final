import shutil
import tempfile
from http import HTTPStatus

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from posts.models import Comment, Group, Post

User = get_user_model()

# Создаем временную папку для медиа-файлов;
# на момент теста медиа папка будет переопределена
TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class PostImgTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # создаём автора
        cls.user = User.objects.create(
            username='auth'
        )
        # создаём группу
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test_slug',
        )
        # создаём пост
        cls.post = Post.objects.create(
            text='Тестовый текст',
            author=cls.user,
            group=cls.group,
        )

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        # Создаем неавторизованный клиент
        self.guest_client = Client()
        # Создаем пользователя
        self.user = PostImgTests.user
        # Создаем второй клиент
        self.authorized_client = Client()
        # Авторизуем пользователя
        self.authorized_client.force_login(self.user)

    def test_context_images(self):
        ''' Тест на добавление картинки на страницы  '''
        # Подсчитаем количество записей в Post
        post_count = Post.objects.count()
        # Создаём картинку
        small_gif = (
            b'\x47\x49\x46\x38\x39\x61\x02\x00'
            b'\x01\x00\x80\x00\x00\x00\x00\x00'
            b'\xFF\xFF\xFF\x21\xF9\x04\x00\x00'
            b'\x00\x00\x00\x2C\x00\x00\x00\x00'
            b'\x02\x00\x01\x00\x00\x02\x02\x0C'
            b'\x0A\x00\x3B'
        )
        # Загружаем картинку
        uploaded = SimpleUploadedFile(
            name='small.gif',
            content=small_gif,
            content_type='image/gif'
        )
        post = Post.objects.create(
            text='Тестовый text',
            author=self.user,
            group=self.group,
            image=uploaded,
        )
        urls = [
            reverse('posts:index'),
            reverse('posts:profile', kwargs={'username': self.user}),
            reverse('posts:group_posts', kwargs={'slug': 'test_slug'}),
        ]
        # Проверяем, увеличилось ли число постов
        self.assertEqual(Post.objects.count(), post_count + 1)
        # Проверяем передаётся ли изображение в контексте
        for url in urls:
            with self.subTest(url=url):
                response = self.authorized_client.get(url)
                self.assertEqual(
                    response.context['page_obj'][0].image, post.image)
        # Проверяем передаётся ли изображение в контексте post_detail
        url_post_detail = reverse('posts:post_detail',
                                  kwargs={'post_id': post.id})
        response = self.authorized_client.get(url_post_detail)
        self.assertEqual(response.context['post'].image, post.image)


class PostCreateFormTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # создаём автора
        cls.user = User.objects.create(
            username='auth'
        )
        # создаём группу
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test_slug',
        )
        # создаём пост
        cls.post = Post.objects.create(
            text='Тестовый текст',
            author=cls.user,
            group=cls.group,
        )
        # создаём комментарий
        cls.comment = Comment.objects.create(
            text='Тестовый комментарий',
            author=cls.user,
            post=cls.post
        )

    def setUp(self):
        # Создаем неавторизованный клиент
        self.guest_client = Client()
        # Создаем пользователя
        self.user = PostCreateFormTests.user
        # Создаем второй клиент
        self.authorized_client = Client()
        # Авторизуем пользователя
        self.authorized_client.force_login(self.user)

    def test_create_post(self):
        ''' Тест на создание новой записи в БД при добавлении нового поста '''
        # Подсчитаем количество записей в Post
        post_count = Post.objects.count()
        form_data = {
            'text': 'Новый пост',
            'group': self.group.id,
        }
        # Отправляем POST-запрос
        response = self.authorized_client.post(
            reverse('posts:post_create'),
            data=form_data,
            follow=True
        )
        # Проверяем, сработал ли редирект
        self.assertRedirects(response, reverse('posts:profile',
                             kwargs={'username': self.user}))
        # Проверяем, увеличилось ли число постов
        self.assertEqual(Post.objects.count(), post_count + 1, (
            ' Пост не добавлен '
        ))

    def test_edit_post(self):
        """ Тест на изменения поста после редактирования """
        new_group = Group.objects.create(title='new_group', slug='new_group')
        form_data = {
            'text': 'новый текст',
            'group': new_group.id,
        }
        response = self.authorized_client.post(reverse(
            'posts:post_edit',
            kwargs={
                'post_id': self.post.id
            }),
            data=form_data,
            follow=True
        )
        edited_post = response.context['post']
        self.post.refresh_from_db()
        self.assertEqual(self.post, edited_post, (
            ' Пост не отредактирован '
        ))

    def test_guest_user_cant_comment(self):
        """ Оставлять комментарий может только авторизованный пользователь """
        comment_count = Comment.objects.count()
        form_data = {
            'text': 'Тестовый comment',
            'author': self.user,
            'post': self.post
        }
        # Отправляем POST-запрос
        response = self.guest_client.post(
            reverse('posts:add_comment', kwargs={'post_id': self.post.id}),
            data=form_data,
            follow=True
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(Comment.objects.count(), comment_count)

    def test_comment_on_the_post_page(self):
        form_data = {
            'text': 'Тестовый comment',
            'author': self.user,
            'post': self.post
        }
        comment = Comment.objects.create(
            text='Тестовый comment',
            author=self.user,
            post=self.post
        )
        response = self.authorized_client.get(
            reverse('posts:add_comment', kwargs={'post_id': self.post.id}),
            data=form_data,
            follow=True
        )
        self.assertRedirects(response,
                             reverse('posts:post_detail',
                                     kwargs={'post_id': self.post.id}))
        response = self.authorized_client.get(
            reverse('posts:post_detail', kwargs={'post_id': self.post.id}),
            data=form_data,
            follow=True
        )
        self.assertEqual(response.context['comments'][1].text, comment.text)
