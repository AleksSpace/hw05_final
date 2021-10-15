from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse

from posts.models import Follow, Group, Post

User = get_user_model()


class PostPagesTests(TestCase):
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
            group=cls.group
        )

    def setUp(self):
        # очищаем кеш
        cache.clear()
        # Создаем неавторизованный клиент
        self.guest_client = Client()
        # Создаем пользователя
        self.user = PostPagesTests.user
        # Создаем второй клиент
        self.authorized_client = Client()
        # Авторизуем пользователя
        self.authorized_client.force_login(self.user)

    def test_pages_uses_correct_template(self):
        """URL-адрес использует соответствующий шаблон."""
        # Собираем в словарь пары "имя_html_шаблона: reverse(name)"
        templates_pages_names = {
            reverse('posts:index'): 'posts/index.html',
            reverse('posts:group_posts',
                    kwargs={'slug': 'test_slug'}): 'posts/group_list.html',
            reverse('posts:profile',
                    kwargs={'username': self.user}): 'posts/profile.html',
            reverse('posts:post_detail',
                    kwargs={'post_id': self.post.id}):
                        'posts/post_detail.html',
            reverse('posts:post_create'): 'posts/create_post.html',
            reverse('posts:post_edit',
                    kwargs={'post_id': self.post.id}): 'posts/create_post.html'
        }
        # Проверяем, что при обращении к name
        # вызывается соответствующий HTML-шаблон
        for reverse_name, template in templates_pages_names.items():
            with self.subTest(reverse_name=reverse_name):
                response = self.authorized_client.get(reverse_name)
                self.assertTemplateUsed(response, template)

    def test_index_list_page_show_correct_context(self):
        """Шаблон index сформирован с правильным контекстом."""
        response = self.authorized_client.get(reverse('posts:index'))
        response_text = response.context['page_obj'][0].text
        response_author = response.context['page_obj'][0].author
        response_group = response.context['page_obj'][0].group
        self.assertEqual(response_text, 'Тестовый текст')
        self.assertEqual(response_author.username, 'auth')
        self.assertEqual(response_group.title, 'Тестовая группа')

    def test_post_on_the_home_page(self):
        """ Тест на появление поста на главной странице после создания """
        response = self.authorized_client.get(reverse('posts:index'))
        test_post = response.context['page_obj'].object_list[0]
        self.assertEqual(self.post, test_post, (
            "Пост не добавился на главную страницу"
        ))

    def test_post_on_the_group_page(self):
        """ Тест на появление поста на странице группы после создания """
        response = self.authorized_client.get(reverse(
            'posts:group_posts',
            kwargs={'slug': 'test_slug'}
        ))
        test_post = response.context['page_obj'].object_list[0]
        self.assertEqual(self.post, test_post, (
            "Пост не добавился на страницу группы"
        ))

    def test_post_not_belongs_to_someone_else_group(self):
        """ Тест на принадлежность поста нужной группе """
        alien_group = Group.objects.create(
            title='alien',
            slug='alien_slug',
            description='alien_desc'
        )
        response = self.authorized_client.get(reverse(
            'posts:group_posts',
            kwargs={'slug': alien_group.slug}))
        alien_posts = response.context['page_obj']
        self.assertNotIn(self.post, alien_posts, (
            ' Пост принадлежит чужой группе '
        ))

    def test_profile_correct_context(self):
        """ Тест на появление поста на странице пользователя """
        response = self.authorized_client.get(reverse(
            'posts:profile',
            kwargs={'username': self.user}
        ))
        test_author = response.context['author']
        posts = response.context['page_obj']
        self.assertEqual(test_author, self.user, (' Указан неверный автор '))
        self.assertIn(self.post, posts, (
            ' Пост автора не отображается на странице автора '
        ))

    def test_cache(self):
        posts_count = Post.objects.count()
        post = Post.objects.create(
            text='Тестовый text',
            author=self.user,
            group=self.group
        )
        response = self.authorized_client.get(reverse('posts:index'))
        response_posts_count = len(response.context['page_obj'])
        # Берем закешированный контент со старницы (там html)
        response_content_cached = response.content
        self.assertEqual(response_posts_count, posts_count + 1)
        # удаляем пост
        post.delete()
        response = self.authorized_client.get(reverse('posts:index'))
        # т.к. страница закеширована и запрос сделать не сможем проверяем
        # только контекст
        # контекст остается такой же
        self.assertEqual(response_content_cached, response.content)
        # чистим кэш
        cache.clear()
        # делаем запрос (помним мы удалили пост
        # значит должен измениться контекст)
        response = self.authorized_client.get(reverse('posts:index'))
        # проверяем что первоначальный контекст с текущим уже не бьет
        self.assertNotEqual(response_content_cached, response.content)


class TestFollowViews(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create(
            username='user'
        )
        cls.author = User.objects.create(
            username='auth'
        )
        cls.post = Post.objects.create(
            text='Тестовый пост',
            author=TestFollowViews.author
        )

    def setUp(self):
        cache.clear()
        self.user = TestFollowViews.user
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)

    def test_auth_follow(self):
        """ Авторизованный пользователь может подписываться на других
            пользователей.
        """
        # Подписался на автора
        self.authorized_client.get(
            reverse(
                'posts:profile_follow',
                args=[TestFollowViews.author],))
        create_follow = Follow.objects.values_list('user', flat=True)
        self.assertIn(TestFollowViews.user.id, create_follow)

    def test_auth_unfollow(self):
        """ Авторизованный пользователь может отписываться от других
            пользователей.
        """
        # Подписался на автора
        self.authorized_client.get(
            reverse(
                'posts:profile_follow',
                args=[TestFollowViews.author],))
        # Отписался от автора
        self.authorized_client.get(
            reverse(
                'posts:profile_unfollow',
                args=[TestFollowViews.author],))
        create_follow = Follow.objects.values_list('user', flat=True)
        self.assertNotIn(TestFollowViews.user.id, create_follow)

    def test_new_post_follow(self):
        """ Новая запись пользователя появляется в ленте тех, кто на него
            подписан.
        """
        posts_count = Post.objects.count()
        # Подписались на автора
        self.authorized_client.get(
            reverse(
                'posts:profile_follow',
                args=[TestFollowViews.author],))
        response = self.authorized_client.get(
            reverse('posts:follow_index')
        )
        response_posts_count = len(response.context['page_obj'])
        self.assertEqual(posts_count, response_posts_count)

    def test_new_post_unfollow(self):
        """ Новая запись пользователя не появляется в ленте тех,
            кто не подписан на него.
        """
        # Подписались на автора
        self.authorized_client.get(
            reverse(
                'posts:profile_follow',
                args=[TestFollowViews.author],))
        response = self.authorized_client.get(
            reverse('posts:follow_index')
        )
        response_posts_count_follow = len(response.context['page_obj'])
        # отписались от автора
        self.authorized_client.get(
            reverse(
                'posts:profile_unfollow',
                args=[TestFollowViews.author],))
        response = self.authorized_client.get(
            reverse('posts:follow_index')
        )
        response_posts_count_unfollow = len(response.context['page_obj'])
        self.assertEqual(response_posts_count_follow - 1,
                         response_posts_count_unfollow)


class PaginatorViewsTest(TestCase):
    """Тестируем Paginator. Страница должна быть разбита на 10 постов"""
    POSTS_IN_PAGE = 10
    POSTS_COUNT = 13

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create(username='TestUser')
        Post.objects.bulk_create([Post(
            text=f'Тестовое сообщение{i}',
            author=cls.user)
            for i in range(cls.POSTS_COUNT)])

    def test_first_page_contains_ten_records(self):
        """Тестируем Paginator.Первые 10 постов на первой странице index"""
        response = self.client.get(reverse('posts:index'))
        self.assertEqual(
            len(response.context.get('page_obj').object_list),
            self.POSTS_IN_PAGE)

    def test_second_page_contains_three_records(self):
        """Тестируем Paginator.Последние 3 поста на второй странице index"""
        response = self.client.get(reverse('posts:index') + '?page=2')
        self.assertEqual(
            len(response.context.get('page_obj').object_list),
            self.POSTS_COUNT - self.POSTS_IN_PAGE)
