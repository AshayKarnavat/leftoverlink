#app.py
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from math import radians, cos, sin, asin, sqrt
from flask import jsonify
from dotenv import load_dotenv
load_dotenv()
import cloudinary
import cloudinary.uploader
import cloudinary.api
from cloudinary.uploader import upload
from cloudinary.api import delete_resources
from cloudinary import CloudinaryImage
# Import both models now
from models import db, User, FoodPost, Request, Rating

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')

# --- Add this Cloudinary configuration ---
cloudinary.config(
  cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME'),
  api_key = os.environ.get('CLOUDINARY_API_KEY'),
  api_secret = os.environ.get('CLOUDINARY_API_SECRET'),
  secure = True
)
# ---

database_url = os.environ.get('DATABASE_URL')
if database_url:
    # Use the Render PostgreSQL database
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url.replace("postgres://", "postgresql://", 1)
else:
    # Fallback to the local SQLite database
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- NEW: Configuration for file uploads ---
basedir = os.path.abspath(os.path.dirname(__file__))


# ---

db.init_app(app)


login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.context_processor
def inject_google_api_key():
    return dict(GOOGLE_API_KEY=os.environ.get('GOOGLE_API_KEY'))

@app.route("/")
def home():
    if current_user.is_authenticated:
        # NEW QUERY: Filter by status='available' AND approval_status='approved'
        posts = FoodPost.query.filter_by(status='available', approval_status='approved').order_by(FoodPost.post_date.desc()).all()
        return render_template("home.html", username=current_user.username, posts=posts)
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        # --- Change #1: Re-render with data on error, instead of redirecting ---
        if password != confirm_password:
            flash("Passwords do not match!", "error")
            return render_template("register.html", form_data=request.form)

        if User.query.filter_by(username=username).first():
            flash("Username already taken!", "error")
            return render_template("register.html", form_data=request.form)

        if User.query.filter_by(email=email).first():
            flash("Email already exists!", "error")
            return render_template("register.html", form_data=request.form)
        
        # If all checks pass, create the user and redirect to login
        new_user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password)
        )
        db.session.add(new_user)
        db.session.commit()
        flash("Registration successful! Please login.", "success")
        return redirect(url_for("login"))

    # This handles the initial GET request
    return render_template("register.html", form_data={})

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for("home"))
        
        # On error, flash message and re-render with the username
        flash("Invalid username or password", "error")
        return render_template("login.html", form_data=request.form)

    # This handles the initial GET request
    return render_template("login.html", form_data={})

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# --- DELETED THE OLD admin_dashboard() function here ---

# --- START: New unified dashboard() function ---
@app.route('/dashboard')
@login_required
def dashboard():
    user = current_user
    
    # === ADMIN CHECK ===
    if user.is_admin:
        # Fetch data needed for the admin dashboard
        pending_posts = FoodPost.query.filter_by(approval_status='pending').order_by(FoodPost.post_date.asc()).all()
        approved_posts = FoodPost.query.filter_by(approval_status='approved').order_by(FoodPost.post_date.desc()).all()
        
        # Load the dedicated admin template with admin data
        return render_template('admin_dashboard.html', 
                               pending_posts=pending_posts, 
                               approved_posts=approved_posts)
    
    # === REGULAR USER LOGIC (if not an admin) ===
    
    # --- Original Donation and Rating Stats ---
    total_donations = len(user.posts)
    successful_pickups = FoodPost.query.filter_by(author=user, status='claimed').count()
    currently_available = total_donations - successful_pickups
    food_claimed = Request.query.filter_by(requester_id=user.id, status='accepted').count()
    
    # Rating Stats
    rating_counts = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
    for rating in user.ratings_received:
        if rating.score in rating_counts:
            rating_counts[rating.score] += 1
            
    # --- Original Queries for Posts and Requests ---
    my_posts = FoodPost.query.filter_by(author=user).order_by(FoodPost.post_date.desc()).all()
    my_requests = Request.query.filter_by(requester=user).order_by(Request.request_date.desc()).all()
    
    # Load the regular user template with user data
    return render_template(
        'dashboard.html', 
        my_posts=my_posts, 
        my_requests=my_requests,
        total_donations=total_donations,
        successful_pickups=successful_pickups,
        currently_available=currently_available,
        rating_counts=rating_counts,
        food_claimed=food_claimed
    )
# --- END: New unified dashboard() function ---


# ... 
@app.route('/admin/verify_post/<int:post_id>/<action>')
@login_required
def verify_post(post_id, action):
    # 1. Security check: Must be an admin
    if not current_user.is_admin:
        flash("Authorization failed.", "error")
        return redirect(url_for('home'))

    post = FoodPost.query.get_or_404(post_id)
    
    # 2. Validate action and update status
    if action == 'approve':
        post.approval_status = 'approved'
        flash(f"Post '{post.food_name}' approved and is now live.", 'success')
        
    elif action == 'decline':
        # Optional: You might delete the post or just mark it as declined
        post.approval_status = 'declined'
        flash(f"Post '{post.food_name}' declined and will not be shown.", 'info')

    else:
        flash("Invalid verification action.", 'error')
        # Changed redirect from 'admin_dashboard' to 'dashboard' since we are consolidating
        return redirect(url_for('dashboard')) 

    db.session.commit()
    # Changed redirect from 'admin_dashboard' to 'dashboard' since we are consolidating
    return redirect(url_for('dashboard')) 


@app.route("/post_food", methods=["GET", "POST"])
@login_required
def post_food():
    if request.method == "POST":
        # 1. Check for the image file
        if 'image' not in request.files or request.files['image'].filename == '':
            flash('No image file was provided!', 'error')
            return redirect(request.url)

        file_to_upload = request.files['image']

        # 2. Upload the file directly to Cloudinary
        try:
            upload_result = cloudinary.uploader.upload(file_to_upload)
            image_url = upload_result.get('secure_url')
        except Exception as e:
            flash(f'Image upload failed: {e}', 'error')
            return redirect(request.url)

        # 3. Create the database record with the new URL
        new_post = FoodPost(
            food_name=request.form['food_name'],
            description=request.form['description'],
            quantity=request.form['quantity'],
            phone_number=request.form['phone_number'],
            city=request.form['city'],
            lat=float(request.form['lat']),
            lon=float(request.form['lon']),
            image_url=image_url, # << THIS IS THE NEW LINE
            author=current_user
        )
        db.session.add(new_post)
        db.session.commit()
        flash('Food post request sent to admin!', 'success')
        return redirect(url_for('home'))

    # This is for the GET request (first time loading the page)
    return render_template('post_food.html')

@app.route("/post/<int:post_id>")
@login_required
def post_details(post_id):
    # Fetch the specific post by its ID, or show a 404 error if not found
    post = FoodPost.query.get_or_404(post_id)
    return render_template('post_details.html', post=post)

@app.route('/profile/<username>')
@login_required
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    
    # --- Donation Stats ---
    total_donations = len(user.posts)
    successful_pickups = FoodPost.query.filter_by(author=user, status='claimed').count()
    currently_available = total_donations - successful_pickups
     # ADD THIS CALCULATION
    food_claimed = Request.query.filter_by(requester_id=user.id, status='accepted').count()   
    # --- Rating Stats ---
    # Initialize a dictionary to hold the count for each star rating (1 to 5)
    rating_counts = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
    for rating in user.ratings_received:
        if rating.score in rating_counts:
            rating_counts[rating.score] += 1

    return render_template(
        'profile.html', 
        user=user, 
        total_donations=total_donations,
        successful_pickups=successful_pickups,
        currently_available=currently_available,
        rating_counts=rating_counts,
        food_claimed=food_claimed
    )


# --- Helper Function for Distance Calculation ---
def haversine(lat1, lon1, lat2, lon2):
    """
    Calculate the great-circle distance between two points 
    on the earth (specified in decimal degrees)
    """
    # convert decimal degrees to radians 
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    # haversine formula 
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    r = 6371 # Radius of earth in kilometers.
    return c * r



# --- API Endpoint for Nearby Posts ---
@app.route("/api/nearby_posts")
@login_required
def nearby_posts():
    # Get user's location and radius from request arguments
    try:
        user_lat = float(request.args.get('lat'))
        user_lon = float(request.args.get('lon'))
        radius_km = float(request.args.get('radius_km', 5)) # Default radius is 5 km
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid location or radius parameters."}), 400

    # THIS IS THE CORRECTED LINE
    all_posts = FoodPost.query.filter(FoodPost.status == 'available', FoodPost.approval_status == 'approved').all()

    
    nearby_posts_data = []

    for post in all_posts:
        distance = haversine(user_lat, user_lon, post.lat, post.lon)
        if distance <= radius_km:
            nearby_posts_data.append({
                "id": post.id,
                "food_name": post.food_name,
                "description": post.description,
                "quantity": post.quantity,
                "city": post.city,
                "image_url": post.image_url,
                "author_username": post.author.username
            })
    
    return jsonify(nearby_posts_data)

# Route to create a new request
@app.route('/request_food/<int:post_id>', methods=['POST'])
@login_required
def request_food(post_id):
    post = FoodPost.query.get_or_404(post_id)
    # Prevent user from requesting their own post
    if post.author.id == current_user.id:
        flash('You cannot request your own food post.', 'error')
        return redirect(url_for('post_details', post_id=post.id))
    
    # Prevent duplicate requests
    existing_request = Request.query.filter_by(requester_id=current_user.id, food_id=post.id).first()
    if existing_request:
        flash('You have already requested this item.', 'info')
        return redirect(url_for('post_details', post_id=post.id))

    new_request = Request(requester_id=current_user.id, food_id=post.id)
    db.session.add(new_request)
    db.session.commit()
    flash('Your request has been sent to the donor!', 'success')
    return redirect(url_for('post_details', post_id=post.id))


@app.route('/search')
@login_required
def search():
    return render_template('search.html')

# Route to accept or decline a request
@app.route('/handle_request/<int:request_id>/<action>')
@login_required
def handle_request(request_id, action):
    req = Request.query.get_or_404(request_id)
    # Security check
    if req.food_post.author.id != current_user.id:
        flash('You are not authorized to perform this action.', 'error')
        return redirect(url_for('home'))

    if action == 'accept':
        req.status = 'accepted'
        
        # --- NEW LOGIC ---
        # Mark the food post as claimed
        req.food_post.status = 'claimed'
        
        # Decline all other pending requests for this food post
        for other_request in req.food_post.requests:
            if other_request.status == 'pending':
                other_request.status = 'declined'
        # --- END NEW LOGIC ---

        flash(f"You have accepted the request from {req.requester.username}. The post is now marked as claimed.", 'success')

    elif action == 'decline':
        req.status = 'declined'
        flash(f"You have declined the request from {req.requester.username}.", 'info')
    
    db.session.commit()
    return redirect(url_for('dashboard'))

    
# app.py

@app.route('/delete_post/<int:post_id>', methods=['POST'])
@login_required
def delete_post(post_id):
    post = FoodPost.query.get_or_404(post_id)
    
    # NEW SECURITY CHECK: Allow deletion if current_user is the author OR is an admin
    if post.author.id != current_user.id and not current_user.is_admin:
        flash('You are not authorized to delete this post.', 'error')
        return redirect(url_for('dashboard'))
    
    try:
        # Get the public ID from the image URL to delete it from Cloudinary
        public_id = post.image_url.split('/')[-1].split('.')[0]
        cloudinary.uploader.destroy(public_id)

        # Delete the post from the database
        db.session.delete(post)
        db.session.commit()
        flash('The post has been deleted.', 'success')  # Changed message to be generic for admin
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting post: {e}', 'error')
        
    return redirect(url_for('dashboard'))

@app.route('/edit_post/<int:post_id>', methods=['GET', 'POST'])
@login_required
def edit_post(post_id):
    post = FoodPost.query.get_or_404(post_id)
    
    # Security check
    if post.author.id != current_user.id:
        flash('You are not authorized to edit this post.', 'error')
        return redirect(url_for('home'))

    if request.method == 'POST':
        # Update text fields
        post.food_name = request.form['food_name']
        post.description = request.form['description']
        post.quantity = request.form['quantity']
        post.phone_number = request.form['phone_number']
        
        # Update location
        post.lat = float(request.form['lat'])
        post.lon = float(request.form['lon'])
        post.city = request.form['city']
        
        # Handle optional new image upload
# ...
        if 'image' in request.files:
            file = request.files['image']
            if file.filename != '': # Simply check if a file was actually provided
                
                # Delete old image from Cloudinary
                old_public_id = post.image_url.split('/')[-1].split('.')[0]
                cloudinary.uploader.destroy(old_public_id)

                # Upload new image to Cloudinary
                new_upload_result = cloudinary.uploader.upload(file)
                post.image_url = new_upload_result.get('secure_url')

        db.session.commit()
        flash('Your post has been updated!', 'success')
        return redirect(url_for('dashboard'))

    # For a GET request, show the pre-filled form
    return render_template('edit_post.html', post=post)

# In backend/app.py

@app.route('/submit_rating/<int:request_id>', methods=['POST'])
@login_required
def submit_rating(request_id):
    req = Request.query.get_or_404(request_id)
    score = int(request.form.get('score'))
    comment = request.form.get('comment')  
    # Security checks
    if req.requester_id != current_user.id:
        flash("You can only rate requests you made.", "error")
        return redirect(url_for('dashboard'))
    if req.status != 'accepted':
        flash("You can only rate completed pickups.", "error")
        return redirect(url_for('dashboard'))

    # Prevent duplicate ratings
    existing_rating = Rating.query.filter_by(request_id=request_id, from_user_id=current_user.id).first()
    if existing_rating:
        flash("You have already rated this pickup.", "info")
        return redirect(url_for('dashboard'))

    # Find the user to be rated (the donor)
    donor = req.food_post.author
    
    # Create the new rating
    new_rating = Rating(
        score=score,
        comment=comment,
        from_user_id=current_user.id,
        to_user_id=donor.id,
        request_id=req.id
    )
    db.session.add(new_rating)
    
    # Update the donor's average rating
    total_score = (donor.avg_rating * donor.num_ratings) + score
    donor.num_ratings += 1
    donor.avg_rating = round(total_score / donor.num_ratings, 2)
    
    db.session.commit()
    flash("Thank you for your feedback!", "success")
    return redirect(url_for('dashboard'))

# ---

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
