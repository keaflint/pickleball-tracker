from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
from sqlalchemy import or_, func, extract
from collections import defaultdict
from itsdangerous import URLSafeTimedSerializer
from flask_mail import Mail, Message
from flask_migrate import Migrate
import random
import json
from io import BytesIO
from flask_wtf import FlaskForm
from wtforms import StringField, DateField, SelectField, IntegerField, BooleanField, HiddenField, PasswordField, EmailField
from wtforms.validators import DataRequired, NumberRange, Email, EqualTo
from jinja2 import UndefinedError
from urllib.parse import urlparse
from flask_wtf.csrf import CSRFProtect, CSRFError
from sqlalchemy.sql import text
from flask_talisman import Talisman
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import logging
from logging.handlers import RotatingFileHandler

app = Flask(__name__)

# Add this before other config
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
if not app.config['SECRET_KEY']:
    raise ValueError("No SECRET_KEY set for Flask application")

# Make sure DATABASE_URL is set
if not os.environ.get('DATABASE_URL'):
    raise ValueError("No DATABASE_URL set for Flask application")

# Configure SQLAlchemy for Postgres
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('postgres://', 'postgresql://', 1)

print(f"Using database: {app.config['SQLALCHEMY_DATABASE_URI']}")  # Debug print

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME')
app.config['WTF_CSRF_ENABLED'] = True
app.config['WTF_CSRF_SECRET_KEY'] = os.urandom(24)

# Update session configuration for serverless environment
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
    # Add these new settings
    SESSION_COOKIE_NAME='session',  # Explicit name
    WTF_CSRF_TIME_LIMIT=None,  # Remove time limit on CSRF tokens
    WTF_CSRF_SSL_STRICT=False  # Needed for Vercel
)

# Initialize CSRF protection after config update
csrf = CSRFProtect(app)

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

mail = Mail(app)
ts = URLSafeTimedSerializer(app.config['SECRET_KEY'])

migrate = Migrate(app, db)

# Initialize Talisman with secure defaults
talisman = Talisman(app,
    content_security_policy={
        'default-src': "'self'",
        'script-src': [
            "'self'",
            'https://code.jquery.com',
            'https://cdn.jsdelivr.net',
            'https://cdnjs.cloudflare.com'
        ],
        'style-src': [
            "'self'",
            "'unsafe-inline'",
            'https://fonts.googleapis.com',
            'https://cdn.jsdelivr.net',
            'https://cdnjs.cloudflare.com'
        ],
        'font-src': [
            "'self'",
            'https://fonts.gstatic.com',
            'https://cdnjs.cloudflare.com'
        ]
    },
    force_https=True
)

# Add SSL requirement for Supabase
if not app.debug:
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        "connect_args": {"sslmode": "require"}
    }

# First, define the Follow model
class Follow(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    follower_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    followed_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Then define Achievement and UserAchievement
class Achievement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    icon = db.Column(db.String(50))  # Emoji or icon class
    tier = db.Column(db.String(20))  # bronze, silver, gold
    points = db.Column(db.Integer, default=10)
    criteria_type = db.Column(db.String(50))  # e.g., 'games_played', 'win_streak', etc.
    criteria_value = db.Column(db.Integer)  # The value needed to earn the achievement
    
    def check_earned(self, user):
        """Check if a user has earned this achievement"""
        if UserAchievement.query.filter_by(user_id=user.id, achievement_id=self.id).first():
            return False  # Already earned
            
        # Get user's stats
        stats = calculate_user_stats(user)
        
        # Check different criteria types
        if self.criteria_type == 'games_played':
            return stats['total_games'] >= self.criteria_value
        elif self.criteria_type == 'win_streak':
            return stats['current_streak'] >= self.criteria_value
        elif self.criteria_type == 'perfect_games':
            return stats['perfect_games'] >= self.criteria_value
        elif self.criteria_type == 'comeback_wins':
            return stats['comeback_wins'] >= self.criteria_value
        elif self.criteria_type == 'win_rate':
            return stats['win_rate'] >= self.criteria_value
            
        return False

class UserAchievement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    achievement_id = db.Column(db.Integer, db.ForeignKey('achievement.id'), nullable=False)
    earned_at = db.Column(db.DateTime, default=datetime.utcnow)

class GameHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'), nullable=False)
    action = db.Column(db.String(50), nullable=False)  # e.g., 'create', 'update', 'delete'
    data = db.Column(db.JSON)  # Store game state at this point
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # Who made the change

    def __repr__(self):
        return f'<GameHistory {self.id} {self.action}>'

# Then define the User model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reset_token = db.Column(db.String(100), unique=True)
    reset_token_expiry = db.Column(db.DateTime)
    remember_token = db.Column(db.String(100), unique=True)
    bio = db.Column(db.Text)
    ranking_points = db.Column(db.Integer, default=1000)  # Starting ELO rating
    rank_singles = db.Column(db.Integer)
    rank_doubles = db.Column(db.Integer)
    games_played_singles = db.Column(db.Integer, default=0)
    games_played_doubles = db.Column(db.Integer, default=0)
    
    # Add relationships
    games = db.relationship('Game', 
                          secondary='player_game',
                          backref=db.backref('players', lazy='dynamic'),
                          lazy='dynamic')
    
    # Add followers relationship
    followers = db.relationship('Follow',
                             foreign_keys=[Follow.followed_id],
                             backref=db.backref('followed', lazy='joined'),
                             lazy='dynamic',
                             cascade='all, delete-orphan')
    
    following = db.relationship('Follow',
                             foreign_keys=[Follow.follower_id],
                             backref=db.backref('follower', lazy='joined'),
                             lazy='dynamic',
                             cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_reset_token(self):
        self.reset_token = ts.dumps(self.email, salt='password-reset-salt')
        self.reset_token_expiry = datetime.utcnow() + timedelta(hours=24)
        db.session.commit()
        return self.reset_token

    @staticmethod
    def verify_reset_token(token):
        try:
            email = ts.loads(token, salt='password-reset-salt', max_age=86400)
            return User.query.filter_by(email=email).first()
        except:
            return None

    # Update the games relationship
    created_games = db.relationship('Game', 
                                  backref='game_creator',  # Changed from 'creator' to 'game_creator'
                                  foreign_keys='Game.creator_id')
    
    participated_games = db.relationship('Game',
                                       secondary='player_game',
                                       backref=db.backref('participants', lazy=True),
                                       overlaps="player_games,game",
                                       viewonly=True)
    player_games = db.relationship('PlayerGame',
                                 backref='user',
                                 overlaps="participated_games")

    def is_following(self, user):
        if not user:
            return False
        return self.following.filter_by(followed_id=user.id).first() is not None

    def follow(self, user):
        if not self.is_following(user):
            f = Follow(follower_id=self.id, followed_id=user.id)
            db.session.add(f)

    def unfollow(self, user):
        f = self.following.filter_by(followed_id=user.id).first()
        if f:
            db.session.delete(f)

    def calculate_ranking(self):
        """Update user's ranking based on recent games"""
        K_FACTOR = 32  # How much each game affects rating
        
        # Get recent games
        recent_games = Game.query.join(PlayerGame)\
            .filter(PlayerGame.user_id == self.id)\
            .order_by(Game.date.desc()).limit(50).all()
            
        for game in recent_games:
            opponent_team = []
            user_team = game.get_user_team(self.id)
            
            # Get opponent's average rating (only for registered users)
            for pg in game.player_games:
                if pg.team_number != user_team and pg.user_id is not None:
                    opponent = User.query.get(pg.user_id)
                    if opponent:  # Only add rating if opponent is a registered user
                        opponent_team.append(opponent.ranking_points)
            
            # Skip rating calculation if no registered opponents
            if not opponent_team:
                continue
            
            opponent_rating = sum(opponent_team) / len(opponent_team)
            
            # Calculate expected win probability
            expected = 1 / (1 + 10 ** ((opponent_rating - self.ranking_points) / 400))
            
            # Actual result (1 for win, 0 for loss)
            actual = 1 if game.winner == user_team else 0
            
            # Update rating
            self.ranking_points += K_FACTOR * (actual - expected)
        
        db.session.commit()

    # Add settings relationship at the end of User model
    settings = db.relationship('UserSettings', backref='user', uselist=False)

    def get_follower_count(self):
        return self.followers.count()

    def get_following_count(self):
        return self.following.count()

# Define UserSettings right after User model
class UserSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    notification_settings = db.Column(db.JSON, default=dict)
    privacy_settings = db.Column(db.JSON, default=dict)
    security_settings = db.Column(db.JSON, default=dict)
    
    @staticmethod
    def get_default_notification_settings():
        return {
            'game_invites': True,
            'achievement_alerts': True,
            'follower_notifications': True,
            'challenge_notifications': True,
            'email_notifications': False
        }
    
    @staticmethod
    def get_default_privacy_settings():
        return {
            'profile_visibility': 'public',  # public, friends, private
            'show_stats': True,
            'show_achievements': True,
            'show_game_history': True
        }
    
    @staticmethod
    def get_default_security_settings():
        return {
            'two_factor_enabled': False,
            'login_notifications': True,
            'trusted_devices': [],
            'activity_log_enabled': True
        }

class PlayerGame(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('game.id', name='fk_game_id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', name='fk_user_id'), nullable=True)
    player_name = db.Column(db.String(64), nullable=True)
    team_number = db.Column(db.Integer, nullable=False)  # 1 or 2
    player_position = db.Column(db.Integer, nullable=False)  # 0 or 1 for position in team

    __table_args__ = (
        db.UniqueConstraint('game_id', 'team_number', 'player_position', name='unique_player_position'),
    )

class Game(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    game_type = db.Column(db.String(10), nullable=False)  # 'singles' or 'doubles'
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    team1_score = db.Column(db.Integer, nullable=False)
    team2_score = db.Column(db.Integer, nullable=False)
    winner = db.Column(db.Integer, nullable=False)  # 1 or 2 for team number
    is_public = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Fix the relationship definition
    creator = db.relationship('User', foreign_keys=[creator_id])
    
    # Add new fields for better data organization
    location = db.Column(db.String(200))  # Where the game was played
    duration = db.Column(db.Integer)      # Duration in minutes
    tournament_name = db.Column(db.String(200))  # Optional tournament name
    game_number = db.Column(db.Integer)   # Game number in tournament/series
    weather_conditions = db.Column(db.String(100))  # Weather during outdoor games
    surface_type = db.Column(db.String(50))  # Court surface type
    skill_level = db.Column(db.String(50))  # Skill level of the game
    
    # Add computed properties
    @property
    def point_difference(self):
        return abs(self.team1_score - self.team2_score)
    
    @property
    def total_points(self):
        return self.team1_score + self.team2_score
    
    @property
    def max_point_deficit(self):
        """Calculate the largest point deficit overcome by the winner"""
        if self.winner == 1:
            return max(0, self.team2_score - self.team1_score)
        return max(0, self.team1_score - self.team2_score)
    
    @property
    def is_perfect_game(self):
        """Check if this was a perfect game (11-0)"""
        return (self.winner == 1 and self.team2_score == 0) or \
               (self.winner == 2 and self.team1_score == 0)

    @property
    def is_comeback(self):
        """Check if this was a comeback win (down by 5+ points)"""
        return self.max_point_deficit >= 5
    
    # Relationships with proper overlaps parameters
    player_games = db.relationship('PlayerGame',
                                 backref='game',
                                 cascade="all, delete-orphan",
                                 overlaps="participants")

    # Add to Game model
    history = db.relationship('GameHistory', 
                             backref='game',
                             cascade="all, delete-orphan",
                             order_by="desc(GameHistory.created_at)")

    def get_player_name(self, team, position):
        player_game = PlayerGame.query.filter_by(
            game_id=self.id,
            team_number=team,
            player_position=position
        ).first()
        if player_game and player_game.user:
            return player_game.user.username
        return None

    def get_user_team(self, user_id):
        """Return which team (1 or 2) the user was on"""
        player_game = PlayerGame.query.filter_by(
            game_id=self.id,
            user_id=user_id
        ).first()
        return player_game.team_number if player_game else None

    def is_liked_by(self, user):
        return Like.query.filter_by(user_id=user.id, game_id=self.id).first() is not None
    
    def like_count(self):
        return Like.query.filter_by(game_id=self.id).count()

def create_game_snapshot(game):
    """Create a JSON snapshot of the game's current state"""
    snapshot = {
        'id': game.id,
        'date': game.date.isoformat() if game.date else None,
        'game_type': game.game_type,
        'creator_id': game.creator_id,
        'team1_score': game.team1_score,
        'team2_score': game.team2_score,
        'winner': game.winner,
        'is_public': game.is_public,
        'location': game.location,
        'duration': game.duration,
        'tournament_name': game.tournament_name,
        'surface_type': game.surface_type,
        'players': []
    }
    
    for pg in game.player_games:
        player = User.query.get(pg.user_id)
        if player:
            snapshot['players'].append({
                'id': player.id,
                'username': player.username,
                'team': pg.team_number,
                'position': pg.player_position
            })
    
    return snapshot

def check_achievements(user):
    """Check and award any new achievements for the user"""
    new_achievements = []
    
    # Get all games the user has participated in
    games = Game.query.join(PlayerGame).filter(PlayerGame.user_id == user.id).all()
    
    # Count total games
    total_games = len(games)
    if total_games >= 100:
        achievement = Achievement.query.filter_by(name='Century Player').first()
        if achievement and not UserAchievement.query.filter_by(user_id=user.id, achievement_id=achievement.id).first():
            new_achievement = UserAchievement(user_id=user.id, achievement_id=achievement.id)
            db.session.add(new_achievement)
            new_achievements.append(achievement)
    
    # Count perfect games (11-0)
    perfect_games = sum(1 for game in games if game.is_perfect_game())
    if perfect_games >= 1:
        achievement = Achievement.query.filter_by(name='Perfect Game').first()
        if achievement and not UserAchievement.query.filter_by(user_id=user.id, achievement_id=achievement.id).first():
            new_achievement = UserAchievement(user_id=user.id, achievement_id=achievement.id)
            db.session.add(new_achievement)
            new_achievements.append(achievement)
    
    # Check for comeback wins
    comeback_games = sum(1 for game in games if game.is_comeback())
    if comeback_games >= 1:
        achievement = Achievement.query.filter_by(name='Comeback King').first()
        if achievement and not UserAchievement.query.filter_by(user_id=user.id, achievement_id=achievement.id).first():
            new_achievement = UserAchievement(user_id=user.id, achievement_id=achievement.id)
            db.session.add(new_achievement)
            new_achievements.append(achievement)
    
    if new_achievements:
        db.session.commit()
    
    return new_achievements

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def init_db():
    with app.app_context():
        try:
            # Create the migrations directory
            if not os.path.exists('migrations'):
                os.system('flask db init')
            
            # Generate and apply migrations
            os.system('flask db migrate -m "Initial migration"')
            os.system('flask db upgrade')
            
            print("Database initialized!")
        except Exception as e:
            print(f"Error initializing database: {e}")

@app.errorhandler(UndefinedError)
def handle_undefined_error(error):
    flash('An error occurred while processing the template. Please try again.', 'error')
    return redirect(url_for('home'))

@app.errorhandler(404)
def page_not_found(e):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('errors/500.html'), 500

@app.errorhandler(403)
def forbidden(e):
    return render_template('errors/403.html'), 403

@app.route('/')
def home():
    if current_user.is_authenticated:
        recent_games = Game.query.join(PlayerGame).filter(
            PlayerGame.user_id == current_user.id
        ).order_by(Game.date.desc()).limit(5).all()
    else:
        recent_games = []
        
    return render_template('index.html', recent_games=recent_games)

# Create form classes
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')

class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = EmailField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', 
        validators=[DataRequired(), EqualTo('password')])

class ForgotPasswordForm(FlaskForm):
    email = EmailField('Email', validators=[DataRequired(), Email()])

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        flash('Invalid username or password', 'error')
    return render_template('auth/login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = RegisterForm()
    if form.validate_on_submit():
        # Your existing registration logic
        pass
    return render_template('auth/register.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('home'))

class GameForm(FlaskForm):
    date = DateField('Date', validators=[DataRequired()])
    game_type = SelectField('Game Type', choices=[('singles', 'Singles'), ('doubles', 'Doubles')], validators=[DataRequired()])
    team1_score = IntegerField('Team 1 Score', validators=[DataRequired(), NumberRange(min=0)])
    team2_score = IntegerField('Team 2 Score', validators=[DataRequired(), NumberRange(min=0)])
    player_1_0 = HiddenField('Player 1 Team 1')
    player_1_1 = HiddenField('Player 2 Team 1')
    player_2_0 = HiddenField('Player 1 Team 2')
    player_2_1 = HiddenField('Player 2 Team 2')
    is_public = BooleanField('Share this game publicly')

@app.route('/games/new', methods=['GET', 'POST'])
@login_required
def new_game():
    form = GameForm()
    
    if request.method == 'POST':
        if form.validate_on_submit():
            try:
                # Create new game
                game = Game(
                    date=form.date.data,
                    game_type=form.game_type.data,
                    creator_id=current_user.id,
                    team1_score=form.team1_score.data,
                    team2_score=form.team2_score.data,
                    winner=1 if form.team1_score.data > form.team2_score.data else 2,
                    is_public=form.is_public.data
                )
                
                db.session.add(game)
                
                # Add current user to team 1
                db.session.add(PlayerGame(
                    game=game,
                    user_id=current_user.id,
                    team_number=1,
                    player_position=0
                ))
                
                # Add other players (registered or not)
                if form.game_type.data == 'doubles':
                    # Add teammate
                    teammate = User.query.filter_by(username=form.player_1_1.data).first()
                    db.session.add(PlayerGame(
                        game=game,
                        user_id=teammate.id if teammate else None,
                        player_name=None if teammate else form.player_1_1.data,
                        team_number=1,
                        player_position=1
                    ))
                
                # Add opponent(s)
                opponent = User.query.filter_by(username=form.player_2_0.data).first()
                db.session.add(PlayerGame(
                    game=game,
                    user_id=opponent.id if opponent else None,
                    player_name=None if opponent else form.player_2_0.data,
                    team_number=2,
                    player_position=0
                ))
                
                if form.game_type.data == 'doubles':
                    opponent2 = User.query.filter_by(username=form.player_2_1.data).first()
                    db.session.add(PlayerGame(
                        game=game,
                        user_id=opponent2.id if opponent2 else None,
                        player_name=None if opponent2 else form.player_2_1.data,
                        team_number=2,
                        player_position=1
                    ))
                
                db.session.commit()
                
                # Update rankings only for registered users who have registered opponents
                has_registered_opponents = False
                
                # Check if opponent is registered
                if opponent and opponent.id:
                    has_registered_opponents = True
                    opponent.calculate_ranking()
                
                if form.game_type.data == 'doubles':
                    if teammate and teammate.id:
                        teammate.calculate_ranking()
                    if opponent2 and opponent2.id:
                        has_registered_opponents = True
                        opponent2.calculate_ranking()
                
                # Only update current user's ranking if there are registered opponents
                if has_registered_opponents:
                    current_user.calculate_ranking()
                
                flash('Game successfully recorded!', 'success')
                return redirect(url_for('dashboard'))
                
            except Exception as e:
                db.session.rollback()
                flash(f'An error occurred while saving the game: {str(e)}', 'error')
                
    return render_template('game_form.html', form=form, today=datetime.today())

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        # Your existing forgot password logic
        pass
    return render_template('auth/forgot_password.html', form=form)

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    try:
        email = ts.loads(token, salt='recover-key', max_age=86400)  # Token valid for 24 hours
    except:
        flash('Invalid or expired password reset token.', 'error')
        return redirect(url_for('forgot_password'))
    
    user = User.query.filter_by(email=email).first()
    
    if not user:
        flash('Invalid password reset token.', 'error')
        return redirect(url_for('forgot_password'))
    
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
        else:
            user.set_password(password)
            db.session.commit()
            flash('Your password has been reset. Please log in.', 'success')
            return redirect(url_for('login'))
    
    return render_template('auth/reset_password.html')

@app.route('/dashboard')
@login_required
def dashboard():
    # Get user's recent games
    recent_games = Game.query.join(PlayerGame).filter(
        PlayerGame.user_id == current_user.id
    ).order_by(Game.date.desc()).limit(5).all()
    
    # Get user's stats
    total_games = PlayerGame.query.filter_by(user_id=current_user.id).count()
    wins = Game.query.join(PlayerGame).filter(
        PlayerGame.user_id == current_user.id,
        Game.winner == PlayerGame.team_number
    ).count()
    
    win_rate = (wins / total_games * 100) if total_games > 0 else 0
    
    # Get recent achievements
    recent_achievements = UserAchievement.query.filter_by(
        user_id=current_user.id
    ).order_by(UserAchievement.earned_at.desc()).limit(3).all()
    
    # Get following activity
    following_ids = [f.followed_id for f in current_user.following.all()]
    following_games = Game.query.join(PlayerGame).filter(
        PlayerGame.user_id.in_(following_ids)
    ).order_by(Game.date.desc()).limit(5).all()
    
    return render_template('dashboard.html',
                         recent_games=recent_games,
                         total_games=total_games,
                         wins=wins,
                         win_rate=win_rate,
                         recent_achievements=recent_achievements,
                         following_games=following_games)

@app.route('/games')
@login_required
def games_page():
    # Get user's games
    user_games = Game.query.join(PlayerGame).filter(
        PlayerGame.user_id == current_user.id
    ).order_by(Game.date.desc()).all()
    
    return render_template('games.html', games=user_games)

@app.route('/leaderboard')
@login_required
def leaderboard():
    # Get all users ordered by ranking points
    users = User.query.order_by(User.ranking_points.desc()).all()
    return render_template('leaderboard.html', users=users)

@app.route('/profile')
@login_required
def profile():
    # Get user's recent games
    recent_games = Game.query.join(PlayerGame).filter(
        PlayerGame.user_id == current_user.id
    ).order_by(Game.date.desc()).limit(5).all()
    
    # Get user's stats
    total_games = PlayerGame.query.filter_by(user_id=current_user.id).count()
    wins = Game.query.join(PlayerGame).filter(
        PlayerGame.user_id == current_user.id,
        Game.winner == PlayerGame.team_number
    ).count()
    
    win_rate = (wins / total_games * 100) if total_games > 0 else 0
    
    return render_template('profile.html',
                         user=current_user,
                         recent_games=recent_games,
                         total_games=total_games,
                         wins=wins,
                         win_rate=win_rate)

@app.route('/stats')
@login_required
def stats():
    # Get user's game statistics
    total_games = PlayerGame.query.filter_by(user_id=current_user.id).count()
    wins = Game.query.join(PlayerGame).filter(
        PlayerGame.user_id == current_user.id,
        Game.winner == PlayerGame.team_number
    ).count()
    
    win_rate = (wins / total_games * 100) if total_games > 0 else 0
    
    # Get games by type
    singles_games = Game.query.join(PlayerGame).filter(
        PlayerGame.user_id == current_user.id,
        Game.game_type == 'singles'
    ).count()
    
    doubles_games = Game.query.join(PlayerGame).filter(
        PlayerGame.user_id == current_user.id,
        Game.game_type == 'doubles'
    ).count()
    
    return render_template('stats.html', 
                         total_games=total_games,
                         wins=wins,
                         win_rate=win_rate,
                         singles_games=singles_games,
                         doubles_games=doubles_games)

@app.route('/achievements')
@login_required
def achievements():
    user_achievements = UserAchievement.query.filter_by(
        user_id=current_user.id
    ).order_by(UserAchievement.earned_at.desc()).all()
    
    return render_template('achievements.html', achievements=user_achievements)

@app.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        bio = request.form.get('bio')
        current_password = request.form.get('current_password')
        
        if not current_user.check_password(current_password):
            flash('Current password is incorrect', 'error')
            return render_template('edit_profile.html')
            
        # Check if username is taken by another user
        if username != current_user.username:
            existing_user = User.query.filter_by(username=username).first()
            if existing_user:
                flash('Username already taken', 'error')
                return render_template('edit_profile.html')
        
        # Check if email is taken by another user
        if email != current_user.email:
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                flash('Email already registered', 'error')
                return render_template('edit_profile.html')
        
        current_user.username = username
        current_user.email = email
        current_user.bio = bio
        
        db.session.commit()
        flash('Profile updated successfully', 'success')
        return redirect(url_for('profile'))
        
    return render_template('edit_profile.html')

@app.route('/game/<int:game_id>')
@login_required
def game_detail(game_id):
    game = Game.query.get_or_404(game_id)
    # Check if user is part of this game
    player_game = PlayerGame.query.filter_by(
        game_id=game.id,
        user_id=current_user.id
    ).first()
    
    if not player_game and not game.is_public:
        flash('You do not have permission to view this game', 'error')
        return redirect(url_for('games_page'))
        
    return render_template('game_detail.html', game=game)

@app.route('/user/<username>')
@login_required
def user_profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    
    # Get user's recent games
    recent_games = Game.query.join(PlayerGame).filter(
        PlayerGame.user_id == user.id
    ).order_by(Game.date.desc()).limit(5).all()
    
    # Get user's stats
    total_games = PlayerGame.query.filter_by(user_id=user.id).count()
    wins = Game.query.join(PlayerGame).filter(
        PlayerGame.user_id == user.id,
        Game.winner == PlayerGame.team_number
    ).count()
    
    win_rate = (wins / total_games * 100) if total_games > 0 else 0
    
    is_following = current_user.is_following(user) if current_user.is_authenticated else False
    
    return render_template('user_profile.html',
                         user=user,
                         recent_games=recent_games,
                         total_games=total_games,
                         wins=wins,
                         win_rate=win_rate,
                         is_following=is_following,
                         follower_count=user.get_follower_count(),
                         following_count=user.get_following_count())

@app.route('/follow/<username>')
@login_required
def follow(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('User {} not found.'.format(username), 'error')
        return redirect(url_for('home'))
    if user == current_user:
        flash('You cannot follow yourself!', 'error')
        return redirect(url_for('user_profile', username=username))
    current_user.follow(user)
    db.session.commit()
    flash('You are now following {}!'.format(username), 'success')
    return redirect(url_for('user_profile', username=username))

@app.route('/unfollow/<username>')
@login_required
def unfollow(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('User {} not found.'.format(username), 'error')
        return redirect(url_for('home'))
    if user == current_user:
        flash('You cannot unfollow yourself!', 'error')
        return redirect(url_for('user_profile', username=username))
    current_user.unfollow(user)
    db.session.commit()
    flash('You have unfollowed {}.'.format(username), 'success')
    return redirect(url_for('user_profile', username=username))

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        # Update user settings
        settings_type = request.form.get('settings_type')
        if settings_type == 'notifications':
            current_user.settings.notification_settings = {
                'game_invites': request.form.get('game_invites') == 'on',
                'achievement_alerts': request.form.get('achievement_alerts') == 'on',
                'follower_notifications': request.form.get('follower_notifications') == 'on',
                'email_notifications': request.form.get('email_notifications') == 'on'
            }
        elif settings_type == 'privacy':
            current_user.settings.privacy_settings = {
                'profile_visibility': request.form.get('profile_visibility'),
                'show_stats': request.form.get('show_stats') == 'on',
                'show_achievements': request.form.get('show_achievements') == 'on',
                'show_game_history': request.form.get('show_game_history') == 'on'
            }
        
        db.session.commit()
        flash('Settings updated successfully', 'success')
        return redirect(url_for('settings'))
        
    return render_template('settings.html')

@app.route('/discover')
@login_required
def discover():
    # Get sort and filter parameters from URL
    sort_by = request.args.get('sort', 'recent')  # Default to recent
    filter_by = request.args.get('filter', 'all')  # Default to all
    
    # Base query for public games - include games where creator marked them as public
    base_query = Game.query.filter(Game.is_public == True)
    
    # Apply filter
    if filter_by == 'following':
        # Get IDs of users being followed
        following_ids = [f.followed_id for f in current_user.following.all()]
        # Show games where followed users are either creators or participants
        base_query = base_query.join(PlayerGame).filter(
            or_(
                Game.creator_id.in_(following_ids),
                PlayerGame.user_id.in_(following_ids)
            )
        ).distinct()
    
    # Apply sorting
    if sort_by == 'recent':
        games = base_query.order_by(Game.date.desc(), Game.created_at.desc())
    elif sort_by == 'most_liked':
        games = base_query.outerjoin(Like)\
            .group_by(Game.id)\
            .order_by(func.count(Like.id).desc(), Game.date.desc())
    elif sort_by == 'most_commented':
        games = base_query.outerjoin(Comment)\
            .group_by(Game.id)\
            .order_by(func.count(Comment.id).desc(), Game.date.desc())
    elif sort_by == 'closest_games':
        games = base_query.order_by(
            func.abs(Game.team1_score - Game.team2_score),
            Game.date.desc()
        )
    
    # Get the games
    recent_games = games.limit(20).all()  # Increased limit to show more games
    
    # Get active users - users who have played games in the last 30 days
    active_users = User.query\
        .join(PlayerGame)\
        .join(Game)\
        .filter(Game.date >= (datetime.utcnow() - timedelta(days=30)))\
        .group_by(User.id)\
        .order_by(func.count(Game.id).desc())\
        .limit(5).all()
    
    return render_template('discover.html',
                         recent_games=recent_games,
                         active_users=active_users,
                         current_sort=sort_by,
                         current_filter=filter_by)

@app.route('/users/search')
@login_required
def search_users():
    query = request.args.get('q', '')
    print(f"Search query: {query}")  # Debug print
    
    # Get all users except current user
    users = User.query.filter(
        User.id != current_user.id,  # Exclude current user
        User.username.ilike(f'%{query}%')
    ).all()
    
    print(f"Found users: {[user.username for user in users]}")  # Debug print
    
    results = [
        {
            'label': user.username,
            'value': user.username,
            'registered': True
        } 
        for user in users
    ]
    
    if query and not any(r['value'].lower() == query.lower() for r in results):
        results.append({
            'label': query,
            'value': query,
            'registered': False
        })
    
    print(f"Results: {results}")  # Debug print
    return jsonify(results)

@app.route('/games/all')
@login_required
def all_games():
    # Get all games the user has participated in, ordered by date
    games = Game.query.join(PlayerGame)\
        .filter(PlayerGame.user_id == current_user.id)\
        .order_by(Game.date.desc())\
        .all()
    
    return render_template('all_games.html', games=games)

@app.route('/games/<int:game_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_game(game_id):
    game = Game.query.get_or_404(game_id)
    
    # Check if user is the creator of the game
    if game.creator_id != current_user.id:
        flash('You can only edit games you created.', 'error')
        return redirect(url_for('all_games'))
    
    form = GameForm()
    
    if request.method == 'POST' and form.validate_on_submit():
        try:
            game.date = form.date.data
            game.game_type = form.game_type.data
            game.team1_score = form.team1_score.data
            game.team2_score = form.team2_score.data
            game.winner = 1 if form.team1_score.data > form.team2_score.data else 2
            game.is_public = form.is_public.data
            
            # Update player games
            # ... (similar to new game creation)
            
            db.session.commit()
            flash('Game updated successfully!', 'success')
            return redirect(url_for('all_games'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred while updating the game: {str(e)}', 'error')
    
    # Pre-fill form with existing data
    if request.method == 'GET':
        form.date.data = game.date
        form.game_type.data = game.game_type
        form.team1_score.data = game.team1_score
        form.team2_score.data = game.team2_score
        form.is_public.data = game.is_public
        
        # Pre-fill player names
        for pg in game.player_games:
            if pg.team_number == 1:
                if pg.player_position == 0:
                    form.player_1_0.data = pg.user.username if pg.user else pg.player_name
                else:
                    form.player_1_1.data = pg.user.username if pg.user else pg.player_name
            else:
                if pg.player_position == 0:
                    form.player_2_0.data = pg.user.username if pg.user else pg.player_name
                else:
                    form.player_2_1.data = pg.user.username if pg.user else pg.player_name
    
    return render_template('game_form.html', form=form, edit_mode=True)

@app.route('/games/<int:game_id>/delete', methods=['POST'])
@login_required
def delete_game(game_id):
    game = Game.query.get_or_404(game_id)
    
    # Check if user is the creator of the game
    if game.creator_id != current_user.id:
        return jsonify({
            'success': False,
            'error': 'You can only delete games you created.'
        }), 403
    
    try:
        # Delete associated player_games first (due to foreign key constraints)
        PlayerGame.query.filter_by(game_id=game.id).delete()
        # Delete associated comments and likes
        Comment.query.filter_by(game_id=game.id).delete()
        Like.query.filter_by(game_id=game.id).delete()
        # Delete the game
        db.session.delete(game)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Game deleted successfully'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Add these models after your existing models
class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'), nullable=False)
    
    # Add relationships
    user = db.relationship('User', backref=db.backref('comments', lazy=True))
    game = db.relationship('Game', backref=db.backref('comments', lazy=True))

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Add relationships
    user = db.relationship('User', backref=db.backref('likes', lazy=True))
    game = db.relationship('Game', backref=db.backref('likes', lazy=True))

# Add these routes after your existing routes
@app.route('/games/<int:game_id>/comment', methods=['POST'])
@login_required
def add_comment(game_id):
    game = Game.query.get_or_404(game_id)
    content = request.form.get('content')
    
    if content:
        comment = Comment(
            content=content,
            user_id=current_user.id,
            game_id=game_id
        )
        db.session.add(comment)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'comment': {
                'content': comment.content,
                'username': comment.user.username,
                'created_at': comment.created_at.strftime('%B %d, %Y %I:%M %p'),
                'is_verified': True
            }
        })
    
    return jsonify({'success': False, 'error': 'Comment cannot be empty'})

@app.route('/games/<int:game_id>/like', methods=['POST'])
@login_required
def toggle_like(game_id):
    game = Game.query.get_or_404(game_id)
    like = Like.query.filter_by(user_id=current_user.id, game_id=game_id).first()
    
    if like:
        db.session.delete(like)
        action = 'unliked'
    else:
        like = Like(user_id=current_user.id, game_id=game_id)
        db.session.add(like)
        action = 'liked'
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'action': action,
        'like_count': game.like_count()
    })

# Add this new function to handle CSRF errors
@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    return render_template('errors/400.html', message="CSRF token validation failed. Please try again."), 400

# Initialize database
with app.app_context():
    try:
        db.create_all()
        print("Database created successfully!")
    except Exception as e:
        print(f"Error creating database: {e}")

# Add rate limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# Add specific limits to sensitive routes
@limiter.limit("5 per minute")
@app.route('/login', methods=['POST'])
def login_post():
    # ... existing login code

def maintenance_mode():
    return os.environ.get('MAINTENANCE_MODE', 'false').lower() == 'true'

@app.before_request
def check_maintenance():
    if maintenance_mode() and not request.path.startswith('/static/'):
        return render_template('maintenance.html'), 503

if __name__ == '__main__':
    app.run(debug=True, port=5000)

if not app.debug:
    if not os.path.exists('logs'):
        os.mkdir('logs')
    file_handler = RotatingFileHandler('logs/pickleball.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('Pickleball Tracker startup')