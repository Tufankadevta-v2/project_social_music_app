from rest_framework import serializers
from django.utils import timezone
from .models import Task, SharedTask, TaskParticipation, Achievement, UserAchievement, AchievementProgress
from user_accounts.serializers import UserSerializer


class TaskSerializer(serializers.ModelSerializer):
    """
    Serializer for Task model with validation and computed fields
    """
    days_until_deadline = serializers.ReadOnlyField()
    completion_percentage = serializers.ReadOnlyField()
    is_overdue_computed = serializers.SerializerMethodField()
    points_to_earn = serializers.SerializerMethodField()
    
    class Meta:
        model = Task
        fields = [
            'id', 'title', 'description', 'priority', 'status',
            'deadline', 'points_value', 'is_shared', 'is_private',
            'created_at', 'updated_at', 'completed_at',
            'days_until_deadline', 'completion_percentage',
            'is_overdue_computed', 'points_to_earn'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'completed_at', 'status']
    
    def get_is_overdue_computed(self, obj):
        """Check if task is overdue"""
        return obj.is_overdue()
    
    def get_points_to_earn(self, obj):
        """Get points that would be earned if completed now"""
        if obj.status == 'completed':
            return obj.calculate_completion_points()
        
        # Simulate completion to calculate potential points
        original_status = obj.status
        original_completed_at = obj.completed_at
        
        obj.status = 'completed'
        obj.completed_at = timezone.now()
        
        points = obj.calculate_completion_points()
        
        # Restore original values
        obj.status = original_status
        obj.completed_at = original_completed_at
        
        return points
    
    def validate_deadline(self, value):
        """Validate that deadline is in the future"""
        if value and value <= timezone.now():
            raise serializers.ValidationError("Deadline must be in the future.")
        return value
    
    def validate_points_value(self, value):
        """Validate points value is reasonable"""
        if value < 1 or value > 100:
            raise serializers.ValidationError("Points value must be between 1 and 100.")
        return value
    
    def validate(self, data):
        """Cross-field validation"""
        # If task is shared, it cannot be private
        if data.get('is_shared') and data.get('is_private'):
            raise serializers.ValidationError("Shared tasks cannot be private.")
        
        return data
    
    def create(self, validated_data):
        """Create task with current user as owner"""
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class TaskListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for task lists
    """
    days_until_deadline = serializers.ReadOnlyField()
    is_overdue_computed = serializers.SerializerMethodField()
    
    class Meta:
        model = Task
        fields = [
            'id', 'title', 'priority', 'status', 'deadline',
            'points_value', 'is_shared', 'created_at',
            'days_until_deadline', 'is_overdue_computed'
        ]
    
    def get_is_overdue_computed(self, obj):
        return obj.is_overdue()


class TaskCompletionSerializer(serializers.Serializer):
    """
    Serializer for task completion endpoint
    """
    task_id = serializers.IntegerField()
    completion_notes = serializers.CharField(max_length=500, required=False, allow_blank=True)
    
    def validate_task_id(self, value):
        """Validate that task exists and belongs to user"""
        user = self.context['request'].user
        
        try:
            task = Task.objects.get(id=value, user=user)
        except Task.DoesNotExist:
            raise serializers.ValidationError("Task not found or does not belong to you.")
        
        if task.status == 'completed':
            raise serializers.ValidationError("Task is already completed.")
        
        return value


class TaskParticipationSerializer(serializers.ModelSerializer):
    """
    Serializer for TaskParticipation model
    """
    user = UserSerializer(read_only=True)
    completion_rank = serializers.ReadOnlyField()
    
    class Meta:
        model = TaskParticipation
        fields = [
            'id', 'user', 'status', 'completed_at', 'points_earned',
            'joined_at', 'completion_rank'
        ]
        read_only_fields = ['id', 'status', 'completed_at', 'points_earned', 'joined_at']


class SharedTaskSerializer(serializers.ModelSerializer):
    """
    Serializer for SharedTask model
    """
    task = TaskSerializer(read_only=True)
    creator = UserSerializer(read_only=True)
    participants = TaskParticipationSerializer(source='taskparticipation_set', many=True, read_only=True)
    participant_count = serializers.SerializerMethodField()
    completion_stats = serializers.SerializerMethodField()
    can_add_participants = serializers.SerializerMethodField()
    
    class Meta:
        model = SharedTask
        fields = [
            'id', 'task', 'creator', 'participants', 'is_competitive',
            'max_participants', 'created_at', 'participant_count',
            'completion_stats', 'can_add_participants'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_participant_count(self, obj):
        return obj.get_participant_count()
    
    def get_completion_stats(self, obj):
        return obj.get_completion_stats()
    
    def get_can_add_participants(self, obj):
        return obj.can_add_participant()


class SharedTaskCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating shared tasks
    """
    task_data = TaskSerializer(write_only=True)
    participant_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        allow_empty=True
    )
    
    class Meta:
        model = SharedTask
        fields = ['task_data', 'participant_ids', 'is_competitive', 'max_participants']
    
    def validate_participant_ids(self, value):
        """Validate that all participant IDs are valid users and friends"""
        if len(value) > 50:
            raise serializers.ValidationError("Cannot invite more than 50 participants.")
        
        # Check if all users exist
        from user_accounts.models import User
        from friendships.models import Friendship
        
        existing_users = User.objects.filter(id__in=value)
        if existing_users.count() != len(value):
            raise serializers.ValidationError("Some participant IDs are invalid.")
        
        # Validate friendship with current user (if context available)
        request = self.context.get('request')
        if request and request.user:
            current_user = request.user
            
            # Check if all participants are friends with the current user
            for user_id in value:
                try:
                    participant = User.objects.get(id=user_id)
                    if not Friendship.are_friends(current_user, participant):
                        raise serializers.ValidationError(
                            f"You can only invite friends to shared tasks. "
                            f"User {participant.phone_number} is not your friend."
                        )
                except User.DoesNotExist:
                    continue  # Already handled above
        
        return value
    
    def create(self, validated_data):
        """Create shared task with participants"""
        task_data = validated_data.pop('task_data')
        participant_ids = validated_data.pop('participant_ids', [])
        
        # Create the base task
        task_data['user'] = self.context['request'].user
        task_data['is_shared'] = True
        task = Task.objects.create(**task_data)
        
        # Create the shared task
        validated_data['task'] = task
        validated_data['creator'] = self.context['request'].user
        shared_task = super().create(validated_data)
        
        # Add creator as participant
        TaskParticipation.objects.create(
            shared_task=shared_task,
            user=self.context['request'].user
        )
        
        # Add other participants
        for user_id in participant_ids:
            from user_accounts.models import User
            try:
                user = User.objects.get(id=user_id)
                TaskParticipation.objects.create(
                    shared_task=shared_task,
                    user=user
                )
            except User.DoesNotExist:
                continue  # Skip invalid users
        
        # Create activity feed entry for shared task creation
        try:
            from social_feed.utils import ActivityFeedManager
            ActivityFeedManager.create_shared_task_created_activity(shared_task)
        except ImportError:
            pass  # Social feed not available
        
        return shared_task


class SharedTaskInviteSerializer(serializers.Serializer):
    """
    Serializer for inviting additional participants to existing shared tasks
    """
    participant_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=True,
        allow_empty=False
    )
    
    def validate_participant_ids(self, value):
        """Validate that all participant IDs are valid friends"""
        if len(value) > 20:
            raise serializers.ValidationError("Cannot invite more than 20 participants at once.")
        
        # Check if all users exist
        from user_accounts.models import User
        from friendships.models import Friendship
        
        existing_users = User.objects.filter(id__in=value)
        if existing_users.count() != len(value):
            raise serializers.ValidationError("Some participant IDs are invalid.")
        
        # Validate friendship with current user
        request = self.context.get('request')
        if request and request.user:
            current_user = request.user
            
            # Check if all participants are friends with the current user
            for user_id in value:
                try:
                    participant = User.objects.get(id=user_id)
                    if not Friendship.are_friends(current_user, participant):
                        raise serializers.ValidationError(
                            f"You can only invite friends to shared tasks. "
                            f"User {participant.phone_number} is not your friend."
                        )
                except User.DoesNotExist:
                    continue  # Already handled above
        
        return value
    
    def validate(self, data):
        """Cross-field validation"""
        shared_task = self.context.get('shared_task')
        if not shared_task:
            raise serializers.ValidationError("Shared task context is required.")
        
        participant_ids = data['participant_ids']
        
        # Check if shared task can accommodate new participants
        current_count = shared_task.get_participant_count()
        if current_count + len(participant_ids) > shared_task.max_participants:
            raise serializers.ValidationError(
                f"Cannot add {len(participant_ids)} participants. "
                f"Shared task can only have {shared_task.max_participants} participants total."
            )
        
        # Check if any participants are already in the shared task
        existing_participant_ids = shared_task.participants.values_list('id', flat=True)
        already_participating = set(participant_ids) & set(existing_participant_ids)
        if already_participating:
            raise serializers.ValidationError(
                f"Some users are already participants in this shared task."
            )
        
        return data


class AchievementSerializer(serializers.ModelSerializer):
    """
    Serializer for Achievement model
    """
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    rarity_display = serializers.CharField(source='get_rarity_display', read_only=True)
    unlock_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Achievement
        fields = [
            'id', 'achievement_id', 'name', 'description', 'icon',
            'category', 'category_display', 'points_reward', 'is_active',
            'rarity', 'rarity_display', 'requirements_data',
            'created_at', 'updated_at', 'unlock_count'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_unlock_count(self, obj):
        """Get the number of users who have unlocked this achievement"""
        return obj.user_unlocks.count()


class UserAchievementSerializer(serializers.ModelSerializer):
    """
    Serializer for UserAchievement model
    """
    achievement = AchievementSerializer(read_only=True)
    user = UserSerializer(read_only=True)
    days_since_earned = serializers.SerializerMethodField()
    
    class Meta:
        model = UserAchievement
        fields = [
            'id', 'user', 'achievement', 'earned_at', 'points_awarded',
            'progress_data', 'notification_sent', 'is_featured',
            'days_since_earned'
        ]
        read_only_fields = ['id', 'earned_at', 'points_awarded', 'notification_sent']
    
    def get_days_since_earned(self, obj):
        """Get number of days since achievement was earned"""
        return (timezone.now() - obj.earned_at).days


class AchievementProgressSerializer(serializers.ModelSerializer):
    """
    Serializer for AchievementProgress model
    """
    achievement = AchievementSerializer(read_only=True)
    user = UserSerializer(read_only=True)
    completion_percentage = serializers.ReadOnlyField()
    is_completed = serializers.ReadOnlyField()
    progress_description = serializers.SerializerMethodField()
    
    class Meta:
        model = AchievementProgress
        fields = [
            'id', 'user', 'achievement', 'current_progress', 'target_progress',
            'progress_data', 'completion_percentage', 'is_completed',
            'progress_description', 'last_updated', 'created_at'
        ]
        read_only_fields = ['id', 'last_updated', 'created_at']
    
    def get_progress_description(self, obj):
        """Get human-readable progress description"""
        return f"{obj.current_progress}/{obj.target_progress} - {obj.completion_percentage:.1f}% complete"


class AchievementSummarySerializer(serializers.Serializer):
    """
    Serializer for achievement summary data
    """
    unlocked_achievements = UserAchievementSerializer(many=True, read_only=True)
    total_achievements = serializers.IntegerField(read_only=True)
    unlocked_count = serializers.IntegerField(read_only=True)
    total_points_from_achievements = serializers.IntegerField(read_only=True)
    completion_percentage = serializers.FloatField(read_only=True)
    progress_towards_achievements = AchievementProgressSerializer(many=True, read_only=True)
    
    class Meta:
        fields = [
            'unlocked_achievements', 'total_achievements', 'unlocked_count',
            'total_points_from_achievements', 'completion_percentage',
            'progress_towards_achievements'
        ]


class LeaderboardEntrySerializer(serializers.Serializer):
    """
    Serializer for individual leaderboard entries
    """
    rank = serializers.IntegerField(read_only=True)
    user = UserSerializer(read_only=True)
    primary_metric = serializers.FloatField(read_only=True)
    total_points = serializers.IntegerField(read_only=True)
    total_tasks = serializers.IntegerField(read_only=True)
    first_places = serializers.IntegerField(read_only=True)
    
    # Optional fields based on category
    average_points = serializers.FloatField(read_only=True, required=False)
    win_rate = serializers.FloatField(read_only=True, required=False)
    top_3_finishes = serializers.IntegerField(read_only=True, required=False)
    consistency_rate = serializers.FloatField(read_only=True, required=False)
    average_completion_hours = serializers.FloatField(read_only=True, required=False)
    total_participations = serializers.IntegerField(read_only=True, required=False)
    completed_tasks = serializers.IntegerField(read_only=True, required=False)
    completion_rate = serializers.FloatField(read_only=True, required=False)


class LeaderboardSerializer(serializers.Serializer):
    """
    Serializer for leaderboard data
    """
    period = serializers.CharField(read_only=True)
    category = serializers.CharField(read_only=True)
    category_display = serializers.CharField(read_only=True)
    leaderboard = LeaderboardEntrySerializer(many=True, read_only=True)
    total_participants = serializers.IntegerField(read_only=True)
    primary_metric = serializers.CharField(read_only=True)
    current_user_rank = serializers.IntegerField(read_only=True, required=False)


class UserRankingSerializer(serializers.Serializer):
    """
    Serializer for user ranking data
    """
    user_rank = serializers.IntegerField(read_only=True, allow_null=True)
    user_stats = LeaderboardEntrySerializer(read_only=True, allow_null=True)
    total_participants = serializers.IntegerField(read_only=True)
    period = serializers.CharField(read_only=True)
    category = serializers.CharField(read_only=True)
    friends_only = serializers.BooleanField(read_only=True)


class LeaderboardSummarySerializer(serializers.Serializer):
    """
    Serializer for comprehensive leaderboard summary
    """
    global_rankings = serializers.DictField(read_only=True)
    friends_rankings = serializers.DictField(read_only=True)
    achievements_ranking = serializers.DictField(read_only=True)
    recent_performance = serializers.DictField(read_only=True)


class LeaderboardOptionsSerializer(serializers.Serializer):
    """
    Serializer for leaderboard configuration options
    """
    periods = serializers.ListField(
        child=serializers.DictField(),
        read_only=True
    )
    categories = serializers.ListField(
        child=serializers.DictField(),
        read_only=True
    )