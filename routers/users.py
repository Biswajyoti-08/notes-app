from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import auth
import models
import schemas
from database import get_db

router = APIRouter(tags=["Authentication"])


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
def register(body: schemas.UserRegister, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == body.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )
    user = models.User(
        email=body.email,
        hashed_password=auth.hash_password(body.password),
    )
    db.add(user)
    db.commit()
    return {"message": "User registered successfully"}


@router.post(
    "/login",
    response_model=schemas.TokenResponse,
    summary="Authenticate and receive a JWT token",
)
def login(body: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == body.email).first()
    if not user or not auth.verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = auth.create_access_token(user.id)
    return {"access_token": token, "token_type": "bearer"}
