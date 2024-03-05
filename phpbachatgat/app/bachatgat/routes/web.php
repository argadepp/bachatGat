<?php

use Illuminate\Support\Facades\Route;
use App\Http\Controllers\UserController;
/*
|--------------------------------------------------------------------------
| Web Routes
|--------------------------------------------------------------------------
|
| Here is where you can register web routes for your application. These
| routes are loaded by the RouteServiceProvider within a group which
| contains the "web" middleware group. Now create something great!
|
*/


Route::get('/users', [UserController::class, 'index']);
// Example routes for UserController
Route::resource('users', 'BachatGatGroupController');
// Example routes for UserController
Route::resource('users', 'MembershipController');
// Example routes for UserController
Route::resource('users', 'TransactionController');
// Example routes for UserController
Route::resource('users', 'LoanController');
// Example routes for UserController
Route::resource('users', 'LoanPaymentController');
Route::get('/', function () {
    return view('welcome');
});



