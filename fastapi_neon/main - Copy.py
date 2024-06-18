from contextlib import asynccontextmanager
from typing import Union, Optional, Annotated
from fastapi_neon import settings
from sqlmodel import Field, Session, SQLModel, create_engine, select, Relationship, ForeignKeyConstraint
from fastapi import FastAPI, Depends, HTTPException, Header
from passlib.context import CryptContext
import jwt

# Middleware for auth
def verify_token(token: str = Header(...)):
    try:
        payload = jwt.decode(token, str(settings.SECRET_KEY), algorithms=["HS256"])
        user_id = int(payload.get("id"))
        if not user_id:
            raise HTTPException(status_code=401, detail="User ID not found in token")
        return {"id": user_id}
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


# Use this variable to hash and veirfy user passwords
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class Todo(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    content: str = Field(index=True)
    completed: bool = Field(default=False)
    user_id: int = Field(foreign_key="user.id")
    owner: "User" = Relationship(back_populates='todos')

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    name: str = Field(index=True)
    hashed_password: str = Field()
    todos: list[Todo] = Relationship(back_populates='owner')
    def verify_password(self, password: str):
        return pwd_context.verify(password, self.hashed_password)

connection_string = str(settings.DATABASE_URL).replace(
    "postgresql", "postgresql+psycopg"
)

engine = create_engine(
    connection_string, connect_args={"sslmode": "require"}, pool_recycle=300
)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Creating tables..")
    create_db_and_tables()
    yield

app = FastAPI(lifespan=lifespan, title="Hello World API with DB", 
    version="0.0.1",
    servers=[
        {
            "url": "http://0.0.0.0:8000",
            "description": "Development Server"
        }
        ])

def get_session():
    with Session(engine) as session:
        yield session

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.post("/todos/", response_model=Todo)
def create_todo(todo: Todo, current_user: dict = Depends(verify_token), session: Session = Depends(get_session)):
        todo.user_id = current_user["id"]
        session.add(todo)
        session.commit()
        session.refresh(todo)
        return todo

@app.get("/todos/", response_model=list[Todo])
def read_todos(current_user: dict = Depends(verify_token), session: Session = Depends(get_session)):
    user_id = current_user["id"]

    if current_user is None:
        raise HTTPException(status_code=401, detail="Unauthorized")

    todos = session.exec(select(Todo).where(Todo.user_id == user_id)).all()
    return todos

@app.patch('/todos/{id}', response_model=Todo)
def update_todo(id: int, todo: Todo, current_user: Annotated[User, Depends(verify_token)], session: Annotated[Session, Depends(get_session)]):
    existing_todo = session.exec(select(Todo).where(Todo.id == id)).first()
    if not existing_todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    if existing_todo.user_id != current_user['id']:
        raise HTTPException(status_code=403, detail="You are not authorized to update this todo")

    existing_todo.content = todo.content
    session.commit()
    session.refresh(existing_todo)
    return existing_todo
@app.delete('/todos/{id}')
def delete_todo(id: int, current_user: Annotated[User, Depends(verify_token)], session: Annotated[Session, Depends(get_session)]):
    todo = session.exec(select(Todo).where(Todo.id == id)).first()
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    
    if todo.user_id != current_user['id']:
        raise HTTPException(status_code=403, detail="You are not authorized to delete this todo")
    
    session.delete(todo)
    session.commit()
    return "Successfully deleted the todo from the Database"

@app.post("/users/register", response_model=str)
async def register(email: str, name: str, password: str, session: Annotated[Session, Depends(get_session)]):
    existing_user_with_email = session.exec(select(User).where(User.email == email)).first()
    if existing_user_with_email:
        raise HTTPException(status_code=400, detail="Email already exists.")

    hashed_password = pwd_context.hash(password)

    new_user = User(email=email, name=name, hashed_password=hashed_password)

    session.add(new_user)
    session.commit()
    session.refresh(new_user)

    token = jwt.encode({"name": new_user.name, "email": new_user.email,"id": str(new_user.id),"password": hashed_password}, str(settings.SECRET_KEY))
    
    return token

@app.post("/users/login", response_model=str)
async def login(email: str, password: str, session: Annotated[Session, Depends(get_session)]):
    existing_user_with_email = session.exec(select(User).where(User.email == email)).first()
    if not existing_user_with_email:
        raise HTTPException(status_code=400, detail="User not found.")

    if not existing_user_with_email.verify_password(password):
        raise HTTPException(status_code=401, detail="Incorrect password")

    session.refresh(existing_user_with_email)

    token = jwt.encode({"email": existing_user_with_email.email, "password": existing_user_with_email.hashed_password, "id": str(existing_user_with_email.id)}, str(settings.SECRET_KEY))

    return token

@app.patch("/users/me", response_model=User)
async def update_user_info(current_user: Annotated[User, Depends(verify_token)], session: Annotated[Session, Depends(get_session)], email: Optional[str] = None, name: Optional[str] = None, password: Optional[str] = None):
    user_id = current_user["id"]
    user = session.exec(select(User).where(User.id == user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not user.id == current_user["id"]:
        raise HTTPException(status_code=403, detail="You are not authorized to update this user")

    if email:
        user.email = email
    if name:
        user.name = name
    if password:
        user.hashed_password = pwd_context.hash(password)

    session.commit()
    session.refresh(user)

    return user

@app.delete("/users/me")
async def delete_user(current_user: Annotated[User, Depends(verify_token)], session: Annotated[Session, Depends(get_session)]):
    user_id = current_user["id"]
    user = session.exec(select(User).where(User.id == user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not user.id == current_user["id"]:
        raise HTTPException(status_code=403, detail="You are not authorized to delete this user")

    # Delete the user from the database
    session.delete(user)
    session.commit()

    return {"message": "User deleted successfully"}