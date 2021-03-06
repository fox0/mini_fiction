#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pony.orm import select
from flask import current_app, render_template

from mini_fiction.models import Chapter, Story, StoryContributor, StoryComment, NewsComment, NewsItem


def chapters_updates(params):
    # Старая логика, при которой могли выводиться много глав одного рассказа подряд
    # chapters = select(c for c in Chapter if not c.draft and c.story_published and c.order != 1)
    # chapters = chapters.order_by(Chapter.first_published_at.desc(), Chapter.order.desc())
    # chapters = chapters[:current_app.config['CHAPTERS_COUNT']['main']]
    # story_ids = [y.story.id for y in chapters]
    # chapters_stories = select(x for x in Story if x.id in story_ids).prefetch(Story.contributors, StoryContributor.user)[:]
    # chapters_stories = {x.id: x for x in chapters_stories}
    # chapters = [(x, chapters_stories[x.story.id]) for x in chapters]

    chapters = current_app.cache.get('index_updated_chapters')
    if chapters is None:
        # Забираем id последних обновлённых рассказов
        # (главы не берём, так как у одного рассказа их может быть много, а нам нужна всего одна)
        index_updated_story_ids = select((c.story.id, max(c.first_published_at)) for c in Chapter if not c.draft and c.story_published and c.order != 1)
        index_updated_story_ids = [x[0] for x in index_updated_story_ids.order_by(-2)[:current_app.config['CHAPTERS_COUNT']['main']]]

        # Забираем последнюю главу каждого рассказа
        # (TODO: наверняка можно оптимизировать, но не придумалось как)
        latest_chapters = list(select(
            (c.story.id, c.id, c.first_published_at, c.order)
            for c in Chapter
            if not c.draft and c.story_published and c.story.id in index_updated_story_ids
        ).order_by(-3, -4))

        index_updated_chapter_ids = []
        for story_id in index_updated_story_ids:
            for x in latest_chapters:
                if x[0] == story_id:
                    index_updated_chapter_ids.append(x[1])
                    break
        assert len(index_updated_chapter_ids) == len(index_updated_story_ids)

        chapters_objs = Chapter.select(lambda x: x.id in index_updated_chapter_ids)
        chapters_objs = {x.id: x for x in chapters_objs.prefetch(Chapter.story, Story.contributors, StoryContributor.user)}

        # Переводим в более простой формат, близкий к json, чтоб удобнее кэшировать и задел на будущие переделки
        # И попутно сортировка
        chapters = []
        for chapter_id in index_updated_chapter_ids:
            x = chapters_objs[chapter_id]
            chapters.append({
                'id': x.id,
                'order': x.order,
                'title': x.title,
                'autotitle': x.autotitle,
                'first_published_at': x.first_published_at,
                'story': {
                    'id': x.story.id,
                    'title': x.story.title,
                    'first_published_at': x.story.first_published_at,
                    'updated': x.story.updated,
                    'authors': [{
                        'id': a.id,
                        'username': a.username,
                    } for a in x.story.authors]
                }
            })
        current_app.cache.set('index_updated_chapters', chapters, 600)

    return render_template('sidebar/chapters_updates.html', chapters=chapters)


def comments_updates(params):
    comments_html = current_app.cache.get('index_comments_html')

    if not comments_html:
        story_comments = StoryComment.select(lambda x: x.story_published and not x.deleted).order_by(StoryComment.id.desc())
        story_comments = story_comments[:current_app.config['COMMENTS_COUNT']['main']]

        news_comments = NewsComment.select(lambda x: not x.deleted).order_by(NewsComment.id.desc())
        news_comments = news_comments[:current_app.config['COMMENTS_COUNT']['main']]

        comments = [('story', x) for x in story_comments]
        comments += [('news', x) for x in news_comments]
        comments.sort(key=lambda x: x[1].date, reverse=True)
        comments = comments[:current_app.config['COMMENTS_COUNT']['main']]

        comments_html = render_template(
            'includes/comments_list.html',
            comments=comments,
            comments_short=True,
        )

        current_app.cache.set('index_comments_html', comments_html, 3600)

    return render_template('sidebar/comments_updates.html', comments_html=comments_html)


def news(params):
    news_list = list(NewsItem.select().order_by(NewsItem.id.desc())[:3])
    return render_template('sidebar/news.html', news=news_list)
