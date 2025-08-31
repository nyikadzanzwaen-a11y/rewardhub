# RewardHub - Loyalty Management System

## 🚀 Project Overview
RewardHub is an advanced, AI-powered loyalty platform developed by **Fusion Six**, a dynamic team of students from various faculties at Midlands State University. Our platform helps businesses build and manage customer loyalty programs with intelligent features and real-time analytics.

## 🏆 Team Fusion Six
A multidisciplinary team of talented students from Midlands State University:
- **Members**: [List of team members here]
- **Institution**: Midlands State University
- **Faculties Represented**: [List of faculties, e.g., Computing, Business, etc.]

## ✨ Key Features
- **Multi-tenant Architecture**: Support for multiple businesses on a single platform
- **AI-Powered Insights**: Customer segmentation and churn prediction
- **Location-Based Services**: Geofencing for check-ins and rewards
- **Flexible Loyalty Programs**: Customizable rules and reward systems
- **Real-time Analytics**: Track customer engagement and program performance
- **Secure Authentication**: JWT-based authentication system

## 🛠️ Technology Stack
- **Backend**: Django 5.0+
- **Frontend**: HTML, TailwindCSS, JavaScript
- **Database**: PostgreSQL with PostGIS
- **AI/ML**: OpenAI API integration
- **Authentication**: JWT
- **Deployment**: Render

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- PostgreSQL 13+
- Node.js & npm (for frontend assets)

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/nyikadzanzwaen-a11y/rewardhub.git
   cd rewardhub
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up the database:
   ```bash
   python manage.py migrate
   ```

5. Create a superuser:
   ```bash
   python manage.py createsuperuser
   ```

6. Run the development server:
   ```bash
   python manage.py runserver
   ```

## 🌐 Deployment
The application is configured for deployment on Render. Check out the [Render deployment guide](https://render.com/docs/deploy-django) for more details.

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments
- Our mentors and lecturers at Midlands State University
- The Django and Python communities
- All the open-source projects that made this possible

---

<div align="center">
  <p>Built with ❤️ by Team Fusion Six | Midlands State University</p>
  <p>© 2025 RewardHub. All rights reserved.</p>
</div>
