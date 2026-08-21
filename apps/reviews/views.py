from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.http import JsonResponse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.utils import timezone
from django.db.models import Avg, Count

from .models import Review
from movies.models import Movie
from bookings.models import Booking


def check_user_review_eligibility(user, movie):
    """
    Checks if a user is eligible to rate/review a movie.
    Requirement: User must have a CONFIRMED booking for a show that has already started/completed.
    """
    if not user or not user.is_authenticated:
        return False
    return Booking.objects.filter(
        user=user,
        show__movie=movie,
        status='CONFIRMED',
        show__start_time__lte=timezone.now()
    ).exists()


class MovieReviewsListAPIView(View):
    """
    API returning reviews, rating breakdown, average rating, and verified status for a movie.
    GET /reviews/api/movie/<int:movie_id>/
    """
    def get(self, request, movie_id):
        movie = get_object_or_404(Movie, pk=movie_id)

        reviews_qs = Review.objects.filter(movie=movie).select_related('user').order_by('-created_at')

        total_reviews = reviews_qs.count()
        avg_rating = reviews_qs.aggregate(avg=Avg('rating'))['avg'] or 0.0

        # Rating distribution breakdown (counts for 1..10)
        dist_raw = reviews_qs.values('rating').annotate(count=Count('id'))
        dist_dict = {i: 0 for i in range(1, 11)}
        for item in dist_raw:
            dist_dict[item['rating']] = item['count']

        user_eligible = check_user_review_eligibility(request.user, movie)

        reviews_data = []
        for r in reviews_qs[:20]:
            is_verified = check_user_review_eligibility(r.user, movie)
            reviews_data.append({
                'id': r.id,
                'user_name': r.user.get_full_name() or r.user.username,
                'user_avatar': r.user.avatar.url if r.user.avatar else '/static/images/default_avatar.png',
                'rating': r.rating,
                'headline': r.headline,
                'comment': r.comment,
                'is_spoiler': r.is_spoiler,
                'is_verified_viewer': is_verified,
                'created_at': r.created_at.strftime('%b %d, %Y')
            })

        return JsonResponse({
            'success': True,
            'movie_id': movie.id,
            'average_rating': float(round(avg_rating, 1)),
            'total_reviews': total_reviews,
            'rating_distribution': dist_dict,
            'user_eligible': user_eligible,
            'reviews': reviews_data
        })


class CreateOrUpdateReviewAPIView(LoginRequiredMixin, View):
    """
    Submit or update user review. Enforces verified viewer eligibility check.
    POST /reviews/api/movie/<int:movie_id>/add/
    """
    def post(self, request, movie_id):
        movie = get_object_or_404(Movie, pk=movie_id)

        # Enforce Verified Viewer Eligibility Rule
        is_eligible = check_user_review_eligibility(request.user, movie)
        if not is_eligible:
            return JsonResponse({
                'success': False,
                'message': 'Only verified viewers who have booked and watched a show for this movie can submit a review.',
                'code': 'NOT_ELIGIBLE'
            }, status=403)

        import json
        try:
            body = json.loads(request.body.decode('utf-8'))
            rating = int(body.get('rating', 0))
            headline = body.get('headline', '').strip()
            comment = body.get('comment', '').strip()
            is_spoiler = bool(body.get('is_spoiler', False))
        except Exception:
            return JsonResponse({'success': False, 'message': 'Invalid request body.'}, status=400)

        if not (1 <= rating <= 10):
            return JsonResponse({'success': False, 'message': 'Rating must be an integer between 1 and 10.'}, status=400)

        if not comment:
            return JsonResponse({'success': False, 'message': 'Review comment cannot be empty.'}, status=400)

        review, created = Review.objects.update_or_create(
            user=request.user,
            movie=movie,
            defaults={
                'rating': rating,
                'headline': headline,
                'comment': comment,
                'is_spoiler': is_spoiler
            }
        )

        # Update aggregate movie rating
        avg_rating = Review.objects.filter(movie=movie).aggregate(avg=Avg('rating'))['avg']
        if avg_rating:
            movie.rating = round(Decimal(str(avg_rating)), 1)
            movie.save(update_fields=['rating'])

        return JsonResponse({
            'success': True,
            'message': 'Review submitted successfully!',
            'review_id': review.id,
            'updated_movie_rating': float(movie.rating)
        })


class ReportReviewAPIView(LoginRequiredMixin, View):
    """
    POST /reviews/api/review/<int:review_id>/report/
    Submits a user report flagging inappropriate content on a review.
    Validates: user cannot report their own review, user cannot submit duplicate reports.
    """
    def post(self, request, review_id):
        import json
        from .models import ReviewReport

        review = get_object_or_404(Review, pk=review_id)

        if review.user_id == request.user.id:
            return JsonResponse({'success': False, 'code': 'SELF_REPORT_DENIED', 'message': 'You cannot report your own review.'}, status=400)

        try:
            if request.content_type == 'application/json':
                body = json.loads(request.body.decode('utf-8'))
                reason = body.get('reason', '').strip()
            else:
                reason = request.POST.get('reason', '').strip()
        except Exception:
            return JsonResponse({'success': False, 'message': 'Invalid request body.'}, status=400)

        if not reason:
            return JsonResponse({'success': False, 'message': 'Reporting reason cannot be empty.'}, status=400)

        report, created = ReviewReport.objects.get_or_create(
            user=request.user,
            review=review,
            defaults={'reason': reason, 'status': 'PENDING'}
        )

        if not created:
            return JsonResponse({'success': False, 'code': 'DUPLICATE_REPORT', 'message': 'You have already reported this review.'}, status=400)

        return JsonResponse({'success': True, 'message': 'Review reported successfully for moderation.', 'report_id': report.id})
