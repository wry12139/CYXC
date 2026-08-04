# Content Management System User Guide

## Overview
The CMS allows admins to manage all course content (knowledge cards, quizzes, terms, articles) without code changes.

## Admin Access
- Default admin account: `admin` / `admin123`
- After first login, change the password
- Admin features appear in "我的" → "课程管理" tab

## Creating Content

1. Click "+新增" button in the course type
2. Fill in the form:
   - **Type**: Select content type (knowledge card, quiz, term, article)
   - **Title**: Course title
   - **Content**: Full content (HTML supported)
   - **Other fields**: Depend on type
3. Click "创建" to save

## Editing Content
1. Click on any content item to select it
2. Edit fields as needed
3. Click "保存" to save changes
4. Version history is automatically tracked

## Viewing Version History
- For each content item, view all changes made over time
- See who changed it and when

## Data Backup
- All content is stored in SQLite database (`finrookie.db`)
- Daily backups are recommended
