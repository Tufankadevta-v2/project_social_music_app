#!/usr/bin/env python3
"""
Script to populate sample data for the social task management application
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'social_task_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from task_management.models import Task, Achievement
from friendships.models import Friendship
from social_feed.models import ActivityFeed
from user_accounts.models import UserProfile
from user_accounts.privacy_models import PrivacySettings

User = get_user_model()

def create_sample_users():
    """Create sample users"""
    users = []
    
    # Create sample users
    user_data = [
        {
            'phone_number': '+1234567890',
            'username': 'alice_smith',
            'display_name': 'Alice Smith',
            'bio': 'Productivity enthusiast and goal achiever!'
        },
        {
            'phone_number': '+1234567891', 
            'username': 'bob_jones',
            'display_name': 'Bob Jones',
            'bio': 'Always up for a challenge and helping friends succeed.'
        },
        {
            'phone_number': '+1234567892',
            'username': 'carol_wilson',
            'display_name': 'Carol Wilson', 
            'bio': 'Fitness lover and task completion champion.'
        },
        {
            'phone_number': '+1234567893',
            'username': 'david_brown',
            'display_name': 'David Brown',
            'bio': 'Tech enthusiast working on personal development.'
        }
    ]
    
    for data in user_data:
        user, created = User.objects.get_or_create(
            phone_number=data['phone_number'],
            defaults={
                'username': data['username'],
                'is_phone_verified': True
            }
        )
        
        # Ensure password and phone verification for demo logins
        if created or not user.has_usable_password():
            user.set_password('defaultpass')
        user.is_phone_verified = True
        user.save()
        
        # Ensure profile exists and is populated
        profile, _ = UserProfile.objects.get_or_create(
            user=user,
            defaults={
                'display_name': data['display_name'],
                'bio': data['bio'],
                'total_points': 0
            }
        )
        if profile.display_name != data['display_name'] or profile.bio != data['bio']:
            profile.display_name = data['display_name']
            profile.bio = data['bio']
            profile.save()
        
        users.append(user)
    
    return users

def create_friendships(users):
    """Create friendships between users"""
    friendships = [
        (users[0], users[1]),  # Alice <-> Bob
        (users[0], users[2]),  # Alice <-> Carol
        (users[1], users[2]),  # Bob <-> Carol
        (users[1], users[3]),  # Bob <-> David
    ]
    
    for requester, addressee in friendships:
        friendship, created = Friendship.objects.get_or_create(
            requester=requester,
            addressee=addressee,
            defaults={'status': 'accepted'}
        )
        
        if created:
            print(f"Created friendship: {requester.username} <-> {addressee.username}")

def create_sample_tasks(users):
    """Create sample tasks for users"""
    task_data = [
        # Alice's tasks
        {
            'user': users[0],
            'title': 'Complete morning workout',
            'description': 'Do 30 minutes of cardio and strength training',
            'priority': 'high',
            'status': 'completed',
            'points_value': 20
        },
        {
            'user': users[0],
            'title': 'Read 20 pages of productivity book',
            'description': 'Continue reading "Atomic Habits"',
            'priority': 'medium',
            'status': 'pending',
            'points_value': 15
        },
        {
            'user': users[0],
            'title': 'Meal prep for the week',
            'description': 'Prepare healthy meals for Monday-Friday',
            'priority': 'medium',
            'status': 'pending',
            'points_value': 25
        },
        
        # Bob's tasks
        {
            'user': users[1],
            'title': 'Learn new programming concept',
            'description': 'Study Django REST framework documentation',
            'priority': 'high',
            'status': 'completed',
            'points_value': 30
        },
        {
            'user': users[1],
            'title': 'Call mom and dad',
            'description': 'Weekly family check-in call',
            'priority': 'high',
            'status': 'pending',
            'points_value': 10
        },
        {
            'user': users[1],
            'title': 'Organize home office',
            'description': 'Clean and reorganize workspace',
            'priority': 'low',
            'status': 'pending',
            'points_value': 15
        },
        
        # Carol's tasks
        {
            'user': users[2],
            'title': 'Run 5K',
            'description': 'Morning run in the park',
            'priority': 'high',
            'status': 'completed',
            'points_value': 25
        },
        {
            'user': users[2],
            'title': 'Practice yoga',
            'description': '45-minute yoga session',
            'priority': 'medium',
            'status': 'completed',
            'points_value': 20
        },
        {
            'user': users[2],
            'title': 'Plan weekend hiking trip',
            'description': 'Research trails and pack gear',
            'priority': 'medium',
            'status': 'pending',
            'points_value': 15
        },
        
        # David's tasks
        {
            'user': users[3],
            'title': 'Update LinkedIn profile',
            'description': 'Add recent projects and skills',
            'priority': 'medium',
            'status': 'pending',
            'points_value': 15
        },
        {
            'user': users[3],
            'title': 'Practice guitar',
            'description': '30 minutes of guitar practice',
            'priority': 'low',
            'status': 'pending',
            'points_value': 10
        }
    ]
    
    for data in task_data:
        task, created = Task.objects.get_or_create(
            user=data['user'],
            title=data['title'],
            defaults=data
        )
        
        if created:
            print(f"Created task: {data['title']} for {data['user'].username}")
            
            # Update user points for completed tasks
            if data['status'] == 'completed':
                profile = task.user.profile
                profile.total_points += data['points_value']
                profile.save()

def create_sample_achievements():
    """Create sample achievements"""
    achievements_data = [
        {
            'achievement_id': 'first_task',
            'name': 'Getting Started',
            'description': 'Complete your first task',
            'icon': '🎯',
            'category': 'milestone',
            'points_reward': 10,
            'rarity': 'common'
        },
        {
            'achievement_id': 'task_streak_3',
            'name': 'On a Roll',
            'description': 'Complete 3 tasks in a row',
            'icon': '🔥',
            'category': 'consistency',
            'points_reward': 25,
            'rarity': 'uncommon'
        },
        {
            'achievement_id': 'early_bird',
            'name': 'Early Bird',
            'description': 'Complete a task before 8 AM',
            'icon': '🌅',
            'category': 'speed',
            'points_reward': 15,
            'rarity': 'common'
        },
        {
            'achievement_id': 'social_butterfly',
            'name': 'Social Butterfly',
            'description': 'Add 5 friends',
            'icon': '🦋',
            'category': 'social',
            'points_reward': 20,
            'rarity': 'uncommon'
        },
        {
            'achievement_id': 'point_collector',
            'name': 'Point Collector',
            'description': 'Earn 100 total points',
            'icon': '💎',
            'category': 'points',
            'points_reward': 50,
            'rarity': 'rare'
        }
    ]
    
    for data in achievements_data:
        achievement, created = Achievement.objects.get_or_create(
            achievement_id=data['achievement_id'],
            defaults=data
        )
        
        if created:
            print(f"Created achievement: {data['name']}")

def create_sample_activities(users):
    """Create sample activity feed entries"""
    activities_data = [
        {
            'user': users[0],
            'activity_type': 'task_completed',
            'title': 'Completed morning workout',
            'description': 'Alice completed her morning workout and earned 20 points!',
            'points_earned': 20
        },
        {
            'user': users[1],
            'activity_type': 'task_completed',
            'title': 'Learned new programming concept',
            'description': 'Bob completed learning Django REST framework and earned 30 points!',
            'points_earned': 30
        },
        {
            'user': users[2],
            'activity_type': 'task_completed',
            'title': 'Completed 5K run',
            'description': 'Carol finished her 5K run and earned 25 points!',
            'points_earned': 25
        },
        {
            'user': users[2],
            'activity_type': 'task_completed',
            'title': 'Finished yoga session',
            'description': 'Carol completed her yoga practice and earned 20 points!',
            'points_earned': 20
        },
        {
            'user': users[0],
            'activity_type': 'friend_joined',
            'title': 'New friendship',
            'description': 'Alice and Bob are now friends!',
            'points_earned': 0
        }
    ]
    
    for data in activities_data:
        activity, created = ActivityFeed.objects.get_or_create(
            user=data['user'],
            title=data['title'],
            defaults=data
        )
        
        if created:
            print(f"Created activity: {data['title']} for {data['user'].username}")

def main():
    """Main function to populate all sample data"""
    print("🚀 Populating sample data for Social Task Management App...")
    print("=" * 60)
    
    # Create users
    print("\n👥 Creating sample users...")
    users = create_sample_users()
    
    # Create friendships
    print("\n🤝 Creating friendships...")
    create_friendships(users)
    
    # Create achievements
    print("\n🏆 Creating sample achievements...")
    create_sample_achievements()
    
    # Create tasks
    print("\n📋 Creating sample tasks...")
    create_sample_tasks(users)
    
    # Create activities
    print("\n📱 Creating sample activities...")
    create_sample_activities(users)
    
    print("\n" + "=" * 60)
    print("✅ Sample data population completed!")
    print("\nSample users created:")
    for user in users:
        profile = getattr(user, 'profile', None)
        display_name = profile.display_name if profile else user.username
        points = profile.total_points if profile else 0
        print(f"  • {display_name} ({user.phone_number}) - {points} points")
    
    print(f"\nTotal users: {User.objects.count()}")
    print(f"Total tasks: {Task.objects.count()}")
    print(f"Total friendships: {Friendship.objects.count()}")
    print(f"Total achievements: {Achievement.objects.count()}")
    print(f"Total activities: {ActivityFeed.objects.count()}")

if __name__ == '__main__':
    main()