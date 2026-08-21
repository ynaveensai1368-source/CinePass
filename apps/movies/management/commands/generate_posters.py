import os
from PIL import Image, ImageDraw, ImageFont
from django.core.management.base import BaseCommand
from django.conf import settings
from movies.models import Movie

class Command(BaseCommand):
    help = "Generate high-resolution cinematic local poster images for all movies and static fallback poster."

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Generating cinematic local poster images..."))

        static_img_dir = os.path.join(settings.BASE_DIR, 'static', 'images')
        media_poster_dir = os.path.join(settings.MEDIA_ROOT, 'posters')
        os.makedirs(static_img_dir, exist_ok=True)
        os.makedirs(media_poster_dir, exist_ok=True)

        # 1. Create Default Fallback Poster (600x900)
        fallback_path = os.path.join(static_img_dir, 'fallback_poster.png')
        self.create_cinematic_poster(
            file_path=fallback_path,
            title="CINEPASS",
            subtitle="MOVIE POSTER",
            tagline="Official Presentation",
            bg_colors=((15, 23, 42), (225, 29, 72))
        )
        self.stdout.write(self.style.SUCCESS(f"Updated static fallback poster: {fallback_path}"))

        # Color palettes per movie
        palettes = {
            'Dune: Part Two': ((18, 12, 28), (225, 29, 72)),        # Crimson Obsidian
            'Oppenheimer': ((15, 23, 42), (217, 119, 6)),           # Amber Gold
            'Interstellar Quantum': ((10, 25, 47), (14, 165, 233)),  # Deep Cosmic Cyan
            'Kalki 2898 AD': ((24, 16, 40), (168, 85, 247)),        # Mystic Violet
            'Cyberpunk Uprising': ((15, 23, 42), (34, 197, 94)),    # Neon Cyber Emerald
            'The Silent Echo': ((15, 23, 42), (100, 116, 139)),     # Foggy Slate
            'Laughter Unlimited': ((30, 27, 75), (236, 72, 153)),   # Vibrant Pink
            'Galactic Guardians': ((15, 23, 42), (245, 158, 11)),   # Golden Orange
        }

        # 2. Generate posters for all movies in DB
        movies = Movie.objects.all()
        for idx, movie in enumerate(movies):
            bg_pair = palettes.get(movie.title, ((15, 23, 42), (225, 29, 72)))
            filename = f"{movie.slug}.png"
            full_path = os.path.join(media_poster_dir, filename)

            first_genre = movie.genres.first().name if movie.genres.exists() else "Blockbuster"
            self.create_cinematic_poster(
                file_path=full_path,
                title=movie.title.upper(),
                subtitle=f"{first_genre.upper()} • {movie.language.name.upper()}",
                tagline=f"RATING {movie.rating} / 10 • {movie.formatted_duration}",
                bg_colors=bg_pair
            )

            movie.poster = f"posters/{filename}"
            movie.save(update_fields=['poster'])
            self.stdout.write(self.style.SUCCESS(f"Generated cinematic poster for: {movie.title}"))

        self.stdout.write(self.style.SUCCESS("All cinematic posters successfully created!"))

    def create_cinematic_poster(self, file_path, title, subtitle, tagline, bg_colors):
        width, height = 600, 900
        img = Image.new('RGB', (width, height), bg_colors[0])
        draw = ImageDraw.Draw(img)

        c1, c2 = bg_colors[0], bg_colors[1]

        # Draw smooth diagonal radial/linear gradient
        for y in range(height):
            ratio = y / height
            r = int(c1[0] + (c2[0] - c1[0]) * (ratio ** 1.2))
            g = int(c1[1] + (c2[1] - c1[1]) * (ratio ** 1.2))
            b = int(c1[2] + (c2[2] - c1[2]) * (ratio ** 1.2))
            draw.line([(0, y), (width, y)], fill=(r, g, b))

        # Add subtle film frame borders
        draw.rectangle([25, 25, width - 25, height - 25], outline=(255, 255, 255, 90), width=3)
        draw.rectangle([35, 35, width - 35, height - 35], outline=(255, 255, 255, 40), width=1)

        # Center Graphic Badge - Dual Ring Cinema Symbol
        cx, cy = width // 2, 340
        draw.ellipse([cx - 100, cy - 100, cx + 100, cy + 100], fill=(0, 0, 0, 120), outline=(255, 255, 255, 180), width=3)
        draw.ellipse([cx - 85, cy - 85, cx + 85, cy + 85], outline=c2, width=2)
        
        # Inner Star / Play Symbol
        draw.polygon([(cx - 30, cy - 45), (cx - 30, cy + 45), (cx + 45, cy)], fill=(255, 255, 255))

        # Fonts
        try:
            title_font = ImageFont.truetype("arial.ttf", 36)
            sub_font = ImageFont.truetype("arial.ttf", 20)
            tag_font = ImageFont.truetype("arial.ttf", 16)
        except IOError:
            title_font = ImageFont.load_default()
            sub_font = ImageFont.load_default()
            tag_font = ImageFont.load_default()

        # Render Tagline at top
        tag_bbox = draw.textbbox((0, 0), tagline, font=tag_font)
        tw = tag_bbox[2] - tag_bbox[0]
        draw.text(((width - tw) // 2, 75), tagline, fill=(226, 232, 240), font=tag_font)

        # Render Title in upper-middle area
        words = title.split()
        lines = []
        curr = ""
        for w in words:
            if len(curr + " " + w) > 16:
                lines.append(curr.strip())
                curr = w
            else:
                curr += " " + w
        if curr:
            lines.append(curr.strip())

        text_y = 520
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=title_font)
            lw = bbox[2] - bbox[0]
            # Draw shadow
            draw.text(((width - lw) // 2 + 2, text_y + 2), line, fill=(0, 0, 0, 200), font=title_font)
            # Draw main text
            draw.text(((width - lw) // 2, text_y), line, fill=(255, 255, 255), font=title_font)
            text_y += 46

        # Render Subtitle
        sub_bbox = draw.textbbox((0, 0), subtitle, font=sub_font)
        sw = sub_bbox[2] - sub_bbox[0]
        draw.text(((width - sw) // 2, text_y + 15), subtitle, fill=(245, 158, 11), font=sub_font)

        # Save Image
        img.save(file_path, 'PNG')
